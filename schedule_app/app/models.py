from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db
from itsdangerous import URLSafeTimedSerializer
from flask import current_app
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    # optional display name and avatar for improved public profiles
    full_name = db.Column(db.String(255), nullable=True)
    avatar_url = db.Column(db.String(1024), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    confirmed = db.Column(db.Boolean, default=False, nullable=False)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    # track when the last confirmation email was sent to allow rate-limiting resends
    last_confirmation_sent_at = db.Column(db.DateTime, nullable=True)
    # Two-factor authentication (TOTP)
    two_factor_enabled = db.Column(db.Boolean, default=False, nullable=False)
    two_factor_secret = db.Column(db.String(128), nullable=True)
    # JSON-encoded list of hashed backup codes (one-time use)
    two_factor_backup_codes = db.Column(db.Text, nullable=True)

    def generate_backup_codes(self, count: int = 10) -> list[str]:
        """Generate a list of one-time backup codes, store their hashed forms, and return plaintext codes.

        The plaintext codes are only returned once to display to the user.
        """
        import secrets
        import json
        from werkzeug.security import generate_password_hash

        codes = [secrets.token_urlsafe(8) for _ in range(count)]
        hashed = [generate_password_hash(c) for c in codes]
        self.two_factor_backup_codes = json.dumps(hashed)
        try:
            db.session.add(self)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return codes

    def verify_and_consume_backup_code(self, code: str) -> bool:
        """Verify a provided backup code and consume it if valid."""
        import json
        from werkzeug.security import check_password_hash

        if not self.two_factor_backup_codes:
            return False
        try:
            hashed_list = json.loads(self.two_factor_backup_codes)
        except Exception:
            return False
        for i, h in enumerate(hashed_list):
            try:
                if check_password_hash(h, code):
                    # consume
                    hashed_list.pop(i)
                    self.two_factor_backup_codes = json.dumps(hashed_list) if hashed_list else None
                    db.session.add(self)
                    db.session.commit()
                    return True
            except Exception:
                continue
        return False

    events = db.relationship("Event", back_populates="user", cascade="all, delete-orphan")
    # organizations the user belongs to (many-to-many)
    organizations = db.relationship(
        "Organization",
        secondary="organization_members",
        back_populates="members",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self) -> str:
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        return serializer.dumps(self.email, salt=current_app.config.get("SECURITY_PASSWORD_SALT"))

    @staticmethod
    def confirm_token(token: str, expiration: "int | None" = None) -> "str | None":
        expiration = expiration or current_app.config.get("CONFIRM_TOKEN_EXPIRATION", 3600)
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        try:
            email = serializer.loads(token, salt=current_app.config.get("SECURITY_PASSWORD_SALT"), max_age=expiration)
        except Exception:
            return None
        return email


class Event(db.Model):
    __tablename__ = "events"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(255), nullable=True)
    participants = db.Column(db.Text, nullable=True)  # CSV or JSON list of participant emails/usernames
    start_at = db.Column(db.DateTime, nullable=False, index=True)
    end_at = db.Column(db.DateTime, nullable=False, index=True)
    category = db.Column(db.String(64), nullable=True)
    rrule = db.Column(db.String(512), nullable=True)  # RFC5545 RRULE string for recurrence
    timezone = db.Column(db.String(64), nullable=True)
    color = db.Column(db.String(7), nullable=False, default="#4287f5")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="events")
    # Optional organization the event belongs to (shared within organization)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    organization = db.relationship("Organization", back_populates="events")


class Organization(db.Model):
    __tablename__ = "organizations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Members relationship via association table
    members = db.relationship(
        "User",
        secondary="organization_members",
        back_populates="organizations",
    )

    events = db.relationship("Event", back_populates="organization", cascade="all, delete-orphan")


# Association table for organization memberships with role
class OrganizationMember(db.Model):
    __tablename__ = "organization_members"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), primary_key=True)
    role = db.Column(db.String(20), nullable=False, default="member")  # member or admin
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Invitation(db.Model):
    __tablename__ = "invitations"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    invited_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="member")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    accepted = db.Column(db.Boolean, default=False, nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=True)

    organization = db.relationship("Organization", backref="invitations")


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    method = db.Column(db.String(32), nullable=False, default="email")  # email, push, sms
    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    sent = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    event = db.relationship("Event", backref="notifications")
    user = db.relationship("User")


# Participants for events (explicit model rather than CSV in Event.participants)
class EventParticipant(db.Model):
    __tablename__ = "event_participants"
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    email = db.Column(db.String(255), nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending, accepted, declined
    role = db.Column(db.String(32), nullable=False, default="participant")
    invited_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    event = db.relationship("Event", backref="participants_assoc")
    user = db.relationship("User")


class EventComment(db.Model):
    __tablename__ = "event_comments"
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("event_comments.id"), nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    event = db.relationship("Event", backref="comments")
    user = db.relationship("User")
    # self-referential relationship for threads
    replies = db.relationship("EventComment", backref=db.backref("parent", remote_side=[id]))


class Attachment(db.Model):
    __tablename__ = "attachments"
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(128), nullable=True)
    storage_path = db.Column(db.String(1024), nullable=False)  # path on disk or remote storage
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    event = db.relationship("Event", backref="attachments")
    uploader = db.relationship("User")


class Reaction(db.Model):
    __tablename__ = "reactions"
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    emoji = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    event = db.relationship("Event", backref="reactions")
    user = db.relationship("User")


class Retro(db.Model):
    __tablename__ = 'retros'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    q1 = db.Column(db.Text, nullable=True)
    q2 = db.Column(db.Text, nullable=True)
    q3 = db.Column(db.Text, nullable=True)
    next_action = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    event = db.relationship('Event', backref='retros')
    user = db.relationship('User')


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True, index=True)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User')
    event = db.relationship('Event')


# External integrations bookkeeping
class ExternalAccount(db.Model):
    __tablename__ = "external_accounts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    provider = db.Column(db.String(64), nullable=False, index=True)  # e.g. 'google'
    external_id = db.Column(db.String(255), nullable=True, index=True)
    access_token = db.Column(db.Text, nullable=True)
    refresh_token = db.Column(db.Text, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    scope = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref="external_accounts")


class ExternalEventMapping(db.Model):
    __tablename__ = "external_event_mappings"
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(64), nullable=False, index=True)
    provider_event_id = db.Column(db.String(255), nullable=False, index=True)
    external_account_id = db.Column(db.Integer, db.ForeignKey("external_accounts.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    last_synced_at = db.Column(db.DateTime, nullable=True)

    external_account = db.relationship("ExternalAccount", backref="event_mappings")
    event = db.relationship("Event", backref="external_mappings")


class IntegrationLog(db.Model):
    __tablename__ = "integration_logs"
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(64), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("external_accounts.id"), nullable=True)
    level = db.Column(db.String(16), nullable=False, default="info")
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    account = db.relationship("ExternalAccount", backref="logs")


# Role-based access control (RBAC) and groups
class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)


class UserRole(db.Model):
    __tablename__ = "user_roles"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), primary_key=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Group(db.Model):
    __tablename__ = "groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class GroupMember(db.Model):
    __tablename__ = "group_members"
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    role = db.Column(db.String(32), nullable=False, default="member")
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# Add relationships onto User dynamically to avoid ordering issues
User.roles = db.relationship("Role", secondary="user_roles", backref="users")
User.groups = db.relationship("Group", secondary="group_members", backref="members")
