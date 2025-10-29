from __future__ import annotations
from flask import Blueprint, current_app, redirect, request, url_for, session
import requests
from urllib.parse import urlencode
from ..models import ExternalAccount, ExternalEventMapping, Event
from .. import db
from ..utils.crypto import encrypt_value, decrypt_value
from datetime import datetime, timedelta
from typing import Optional

google_bp = Blueprint("integrations_google", __name__, url_prefix="/integrations/google")


def _get_oauth_config():
    client_id = current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET")
    redirect_uri = url_for("integrations_google.oauth_callback", _external=True)
    return client_id, client_secret, redirect_uri


@google_bp.route("/connect")
def oauth_connect():
    client_id, _, redirect_uri = _get_oauth_config()
    if not client_id:
        current_app.logger.error("Google OAuth client id not configured (GOOGLE_OAUTH_CLIENT_ID missing)")
        return "Google OAuth not configured on server", 500
    scope = "https://www.googleapis.com/auth/calendar"
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return redirect(auth_url)


@google_bp.route("/callback")
def oauth_callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400
    client_id, client_secret, redirect_uri = _get_oauth_config()
    if not client_id or not client_secret:
        current_app.logger.error("Google OAuth client credentials missing (client_id=%s client_secret=%s)", bool(client_id), bool(client_secret))
        return "Google OAuth not configured on server", 500
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    resp = requests.post(token_url, data=data, timeout=10)
    if resp.status_code != 200:
        current_app.logger.error("Google token exchange failed: %s %s", resp.status_code, resp.text)
        return "OAuth failed", 400
    token_data = resp.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")
    id_token = token_data.get("id_token")
    # For now, assume user is logged in and current_user available
    from flask_login import current_user
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    # store external account
    ea = ExternalAccount(user_id=current_user.id, provider="google", access_token=access_token, refresh_token=refresh_token)
    if expires_in:
        ea.expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
    # encrypt tokens before saving
    if access_token:
        ea.access_token = encrypt_value(access_token)
    if refresh_token:
        ea.refresh_token = encrypt_value(refresh_token)
    db.session.add(ea)
    db.session.commit()
    return redirect(url_for("events.calendar"))


def refresh_access_token(external_account: ExternalAccount) -> bool:
    """Refresh access token using stored refresh_token. Returns True if refreshed."""
    if not external_account.refresh_token:
        return False
    refresh_token = decrypt_value(external_account.refresh_token)
    if not refresh_token:
        return False
    client_id = current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET")
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    resp = requests.post(token_url, data=data, timeout=10)
    if resp.status_code != 200:
        current_app.logger.error("Failed to refresh google token: %s %s", resp.status_code, resp.text)
        return False
    token_data = resp.json()
    access_token = token_data.get("access_token")
    expires_in = token_data.get("expires_in")
    if access_token:
        external_account.access_token = encrypt_value(access_token)
    if expires_in:
        external_account.expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
    db.session.add(external_account)
    db.session.commit()
    return True


def import_events_for_account(external_account: ExternalAccount, since: Optional[datetime] = None):
    """Fetch primary calendar events and create/update local Event objects.

    This is a minimal example: mapping is naive and should be extended for full coverage.
    """
    headers = {"Authorization": f"Bearer {external_account.access_token}"}
    now = datetime.utcnow()
    time_min = (since or (now - timedelta(days=30))).isoformat() + "Z"
    params = {"timeMin": time_min, "singleEvents": "true", "orderBy": "startTime"}
    resp = requests.get("https://www.googleapis.com/calendar/v3/calendars/primary/events", headers=headers, params=params, timeout=10)
    if resp.status_code != 200:
        current_app.logger.error("Google calendar list failed: %s %s", resp.status_code, resp.text)
        return []
    items = resp.json().get("items", [])
    created = 0
    for it in items:
        provider_event_id = it.get("id")
        mapping = ExternalEventMapping.query.filter_by(provider="google", provider_event_id=provider_event_id, external_account_id=external_account.id).first()
        start = it.get("start", {}).get("dateTime") or it.get("start", {}).get("date")
        end = it.get("end", {}).get("dateTime") or it.get("end", {}).get("date")
        # naive mapping: create event if not mapped
        if not mapping:
            ev = Event(user_id=external_account.user_id, title=it.get("summary") or "(no title)", description=it.get("description"), start_at=datetime.fromisoformat(start.replace("Z", "+00:00")), end_at=datetime.fromisoformat(end.replace("Z", "+00:00")))
            db.session.add(ev)
            db.session.commit()
            mapping = ExternalEventMapping(provider="google", provider_event_id=provider_event_id, external_account_id=external_account.id, event_id=ev.id, last_synced_at=datetime.utcnow())
            db.session.add(mapping)
            db.session.commit()
            created += 1
    return created
