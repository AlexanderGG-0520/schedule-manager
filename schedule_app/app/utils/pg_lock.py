"""Postgres advisory lock context manager and decorator.

Uses PostgreSQL advisory locks (pg_try_advisory_lock / pg_advisory_unlock) to ensure
that a named job only runs in one process at a time. Lock keys should be integers; we compute
a 64-bit key by hashing a string job id.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import text
from .. import db


def _job_key(job_id: str) -> int:
    # produce a stable 64-bit signed integer from the job id
    h = hashlib.sha256(job_id.encode("utf-8")).digest()
    # take first 8 bytes as unsigned, convert to int
    val = int.from_bytes(h[:8], byteorder="big", signed=False)
    # Postgres advisory lock takes bigint (signed), so fit into signed 64-bit
    if val > (2 ** 63 - 1):
        val = val - 2 ** 64
    return val


@contextmanager
def pg_try_advisory_lock(job_id: str) -> Generator[bool, None, None]:
    """Try to acquire advisory lock for job_id. Yields True if lock acquired, False otherwise.

    Usage:
        with pg_try_advisory_lock('cleanup_job') as locked:
            if not locked:
                return
            # perform job
"""
    key = _job_key(job_id)
    conn = db.engine.connect()
    trans = conn.begin()
    locked = False
    try:
        # pg_try_advisory_lock returns boolean
        result = conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key})
        locked = bool(result.scalar())
        yield locked
    finally:
        if 'locked' in locals() and locked:
            try:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
            except Exception:
                pass
        try:
            trans.commit()
        except Exception:
            trans.rollback()
        conn.close()


def single_instance(job_id: str):
    """Decorator to ensure the wrapped function runs only when lock is acquired."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with pg_try_advisory_lock(job_id) as locked:
                if not locked:
                    # another process is running this job
                    return None
                return func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        return wrapper

    return decorator
