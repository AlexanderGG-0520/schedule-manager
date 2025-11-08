#!/usr/bin/env python3
"""
Developer helper: safely replace non-ASCII usernames with ASCII-only placeholders.

Usage:
  python scripts/reset_nonascii_usernames.py --dry-run
  python scripts/reset_nonascii_usernames.py --commit

Features:
 - Finds users whose `username` contains non-ASCII or disallowed characters.
 - Proposes replacements derived from email/full_name or fallback to `user<id>`.
 - Ensures uniqueness by appending numeric suffixes if needed.
 - Dry-run prints proposed changes; --commit applies them in a DB transaction.
 - Writes a backup SQL file of UPDATE statements when committing.

Note: Run in a maintenance window and ensure DB backups before --commit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Iterable


def slugify_username(src: str) -> str:
    """Keep only ASCII letters, digits, dot, underscore and hyphen. Lowercase."""
    if not src:
        return ""
    # Normalize spaces to underscores, remove diacritics conservatively by removing non-ascii
    s = src.strip().lower()
    # replace spaces with underscore
    s = re.sub(r"\s+", "_", s)
    # remove characters except ascii letters/numbers/._-
    s = re.sub(r"[^a-z0-9_.-]", "", s)
    # collapse multiple dots/underscores/hyphens
    s = re.sub(r"[._-]{2,}", "_", s)
    return s or ""


def find_nonascii_users(all_users: Iterable) -> list:
    """Return list of User objects whose username is not ascii or contains disallowed chars."""
    bad = []
    allowed_re = re.compile(r"^[A-Za-z0-9_.-]+$")
    for u in all_users:
        if not isinstance(u.username, str) or not u.username:
            bad.append(u)
            continue
        if not u.username.isascii() or not allowed_re.match(u.username):
            bad.append(u)
    return bad


def propose_username(user, existing_usernames: set) -> str:
    # try full_name -> email local part -> username filtered -> fallback to user<id>
    candidates = []
    if getattr(user, "full_name", None):
        candidates.append(slugify_username(user.full_name))
    if getattr(user, "email", None):
        local = user.email.split("@", 1)[0]
        candidates.append(slugify_username(local))
    # filtered original
    candidates.append(slugify_username(user.username or ""))
    candidates.append(f"user{user.id}")

    for base in candidates:
        if not base:
            continue
        candidate = base
        suffix = 0
        while candidate in existing_usernames:
            suffix += 1
            candidate = f"{base}{suffix}"
        if candidate:
            return candidate
    # as last resort
    i = 1
    while True:
        cand = f"user{user.id}_{i}"
        if cand not in existing_usernames:
            return cand
        i += 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reset non-ASCII usernames safely")
    parser.add_argument("--commit", action="store_true", help="Apply changes (default: dry-run)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of users to process (0 = no limit)")
    parser.add_argument("--backup", default="username_updates_backup.sql", help="Backup SQL file path when committing")
    parser.add_argument("--start-id", type=int, default=0, help="Start from user id >= START_ID")
    args = parser.parse_args(argv)

    # Defer importing heavy app until after parsing
    # Import the app factory and models from the project
    try:
        from schedule_app.app import create_app, db
        from schedule_app.app.models import User
    except Exception as e:
        print("Error importing application factory or models:", e)
        print("Run this script from repo root where package `schedule_app` is importable.")
        sys.exit(2)

    app = create_app()
    with app.app_context():
        # load all usernames into a set for uniqueness checks
        existing = {u.username for u in User.query.with_entities(User.username).all() if u.username}

        # load candidates (we'll filter in Python)
        q = User.query.order_by(User.id)
        if args.start_id:
            q = q.filter(User.id >= args.start_id)
        users = q.all()

        bad = find_nonascii_users(users)
        if args.limit:
            bad = bad[: args.limit]

        if not bad:
            print("No non-ASCII or disallowed usernames found.")
            return

        changes = []  # tuples (user_id, old, new)
        for u in bad:
            new = propose_username(u, existing)
            if new and new != u.username:
                changes.append((u.id, u.username, new))
                existing.add(new)

        # Report
        print("Found {} problematic users".format(len(bad)))
        print()
        for uid, old, new in changes:
            print(f"{uid}: '{old}' -> '{new}'")

        if not args.commit:
            print("\nDry-run complete. No changes applied. Re-run with --commit to apply updates.")
            return

        # Commit changes
        backup_lines = ["-- username updates backup\n", "BEGIN;\n"]
        try:
            for uid, old, new in changes:
                u = User.query.get(uid)
                if not u:
                    print(f"User id {uid} disappeared; skipping")
                    continue
                # double-check uniqueness at commit time
                exists = User.query.filter(User.username == new).first()
                if exists and exists.id != uid:
                    print(f"Conflict: candidate username {new} already exists for user {exists.id}; skipping {uid}")
                    continue
                # prepare SQL backup line
                safe_old = (old or "")
                safe_new = new
                # escape single quotes for SQL literal
                safe_old_escaped = safe_old.replace("'", "''")
                safe_new_escaped = safe_new.replace("'", "''")
                backup_lines.append(
                    f"UPDATE users SET username = '{safe_new_escaped}' WHERE id = {uid} AND username = '{safe_old_escaped}' ;\n"
                )
                # apply
                u.username = new
                db.session.add(u)
            db.session.commit()
            backup_lines.append("COMMIT;\n")
        except Exception as e:
            print("Error during commit, rolling back:", e)
            db.session.rollback()
            backup_lines.append("ROLLBACK;\n")
            # still write backup with ROLLBACK to indicate partial failure

        # write backup file
        try:
            with open(args.backup, "w", encoding="utf-8") as fh:
                fh.writelines(backup_lines)
            print(f"Backup SQL written to {args.backup}")
        except Exception as e:
            print("Failed to write backup file:", e)

        print("Commit finished. Verify integrity and run application tests/staging checks.")


if __name__ == "__main__":
    main()
