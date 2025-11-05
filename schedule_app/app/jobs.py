from __future__ import annotations
from datetime import datetime, timedelta
from typing import Iterable

from . import db
from .models import Notification
from flask import current_app

try:
    # import optional helper for advisory locks
    from .utils.pg_lock import pg_try_advisory_lock
except Exception:  # pragma: no cover - optional
    pg_try_advisory_lock = None  # type: ignore

from .auth.routes import send_email
from .models import ExternalAccount

try:
    from .integrations.google import refresh_access_token as google_refresh_access_token
except Exception:  # optional
    google_refresh_access_token = None  # type: ignore


def _process_notification(n: Notification) -> None:
    try:
        user = n.user
        event = n.event
        subject = f"[Schedule] リマインダー: {event.title}"
        body = (
            f"イベント '{event.title}' のリマインダーです。\n\n"
            f"詳細: {event.description or ''}\n"
            f"場所: {event.location or ''}\n"
            f"開始: {event.start_at}\n終了: {event.end_at}\n"
        )
        ok = send_email(subject, str(user.email), body)
        if ok:
            n.sent = True
            n.sent_at = datetime.utcnow()
            db.session.add(n)
            db.session.commit()
            current_app.logger.info("Notification %s sent", n.id)
        else:
            current_app.logger.error("Notification %s failed to send", n.id)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to process Notification %s", getattr(n, "id", None))


# Job decorator for scheduler auto-discovery
def job(**meta):
    """Decorator to mark a function as a scheduled job.

    Example:
        @job(schedule='interval', minutes=15, id='cleanup_old_events')
        def cleanup_old_events():
            ...
    Supported meta keys: schedule (e.g. 'interval'), id, minutes, seconds, hours
    """

    def _decorator(fn):
        setattr(fn, "job_meta", meta)
        return fn

    return _decorator


def run_due_jobs():
    """Process due notifications and run maintenance jobs.

    This function is intended to be safe to call under a Postgres advisory lock
    (see tasks.py) so that only one process executes it across replicas.
    """
    current_app.logger.info("run_due_jobs: scanning for due notifications")
    now = datetime.utcnow()
    due = (
        Notification.query.filter(Notification.scheduled_at <= now, Notification.sent == False)
        .order_by(Notification.scheduled_at)
        .limit(100)
        .all()
    )
    for n in due:
        _process_notification(n)


@job(schedule="interval", minutes=15, id="cleanup_old_events")
def cleanup_old_events():
    """Trivial cleanup job: remove events that are completely in the distant past.

    This is a placeholder; adjust retention policy as needed.
    """
    cutoff = datetime.utcnow().replace(year=datetime.utcnow().year - 2)
    # lazy import to avoid circular at module import time
    from .models import Event

    q = Event.query.filter(Event.end_at != None, Event.end_at < cutoff)
    count = q.count()
    if count:
        current_app.logger.info("cleanup_old_events: deleting %s old events", count)
        q.delete(synchronize_session=False)
        db.session.commit()
    else:
        current_app.logger.info("cleanup_old_events: nothing to delete")


@job(schedule="interval", minutes=10, id="refresh_external_accounts")
def refresh_external_accounts():
    """Refresh access tokens for external accounts whose tokens are expired or about to expire.

    This job is intentionally conservative: it will refresh accounts with expires_at within the next 5 minutes.
    """
    current_app.logger.info("refresh_external_accounts: scanning external accounts for refresh")
    now = datetime.utcnow()
    threshold = now + timedelta(minutes=5)
    accounts = ExternalAccount.query.filter(ExternalAccount.expires_at != None, ExternalAccount.expires_at <= threshold).all()
    for a in accounts:
        try:
            if a.provider == "google" and google_refresh_access_token:
                ok = google_refresh_access_token(a)
                current_app.logger.info("refreshed google account %s ok=%s", a.id, ok)
            else:
                current_app.logger.info("no refresh handler for provider %s", a.provider)
        except Exception:
            current_app.logger.exception("failed to refresh external account %s", a.id)
