from __future__ import annotations
from flask import Blueprint, current_app, redirect, request, url_for
import requests
from urllib.parse import urlencode
from ..models import ExternalAccount, ExternalEventMapping, Event
from .. import db
from datetime import datetime, timedelta
from typing import Optional
from ..utils.crypto import encrypt_value, decrypt_value

outlook_bp = Blueprint("integrations_outlook", __name__, url_prefix="/integrations/outlook")


def _get_oauth_config():
    client_id = current_app.config.get("OUTLOOK_OAUTH_CLIENT_ID")
    client_secret = current_app.config.get("OUTLOOK_OAUTH_CLIENT_SECRET")
    redirect_uri = url_for("integrations_outlook.oauth_callback", _external=True)
    return client_id, client_secret, redirect_uri


@outlook_bp.route("/connect")
def oauth_connect():
    client_id, _, redirect_uri = _get_oauth_config()
    scope = "https://graph.microsoft.com/Calendars.ReadWrite offline_access openid profile email"
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": scope,
        "prompt": "consent",
    }
    auth_url = f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{urlencode(params)}"
    return redirect(auth_url)


@outlook_bp.route("/callback")
def oauth_callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400
    client_id, client_secret, redirect_uri = _get_oauth_config()
    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    resp = requests.post(token_url, data=data, timeout=10)
    if resp.status_code != 200:
        current_app.logger.error("Outlook token exchange failed: %s %s", resp.status_code, resp.text)
        return "OAuth failed", 400
    token_data = resp.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")
    from flask_login import current_user
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    ea = ExternalAccount(user_id=current_user.id, provider="outlook")
    if expires_in:
        ea.expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
    if access_token:
        ea.access_token = encrypt_value(access_token)
    if refresh_token:
        ea.refresh_token = encrypt_value(refresh_token)
    db.session.add(ea)
    db.session.commit()
    return redirect(url_for("integrations.index"))


def refresh_access_token(external_account: ExternalAccount) -> bool:
    if not external_account.refresh_token:
        return False
    refresh_token = decrypt_value(external_account.refresh_token)
    if not refresh_token:
        return False
    client_id = current_app.config.get("OUTLOOK_OAUTH_CLIENT_ID")
    client_secret = current_app.config.get("OUTLOOK_OAUTH_CLIENT_SECRET")
    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    resp = requests.post(token_url, data=data, timeout=10)
    if resp.status_code != 200:
        current_app.logger.error("Failed to refresh outlook token: %s %s", resp.status_code, resp.text)
        return False
    td = resp.json()
    access_token = td.get("access_token")
    expires_in = td.get("expires_in")
    if access_token:
        external_account.access_token = encrypt_value(access_token)
    if expires_in:
        external_account.expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
    db.session.add(external_account)
    db.session.commit()
    return True


def import_events_for_account(external_account: ExternalAccount, since: Optional[datetime] = None):
    """Import events from Microsoft Graph /me/events into local Events (naive mapping)."""
    access_token_enc = external_account.access_token
    if not access_token_enc:
        return 0
    access_token = decrypt_value(access_token_enc)
    if not access_token:
        return 0
    headers = {"Authorization": f"Bearer {access_token}", "Prefer": "outlook.timezone=UTC"}
    now = datetime.utcnow()
    time_min = (since or (now - timedelta(days=30))).isoformat() + "Z"
    params = {"startDateTime": time_min, "endDateTime": (now + timedelta(days=365)).isoformat() + "Z"}
    # Graph API to list events in a calendar view: GET /me/calendarview?startDateTime=...&endDateTime=...
    resp = requests.get("https://graph.microsoft.com/v1.0/me/calendarview", headers=headers, params=params, timeout=10)
    if resp.status_code != 200:
        current_app.logger.error("Outlook calendar list failed: %s %s", resp.status_code, resp.text)
        return 0
    items = resp.json().get("value", [])
    created = 0
    for it in items:
        provider_event_id = it.get("id")
        mapping = ExternalEventMapping.query.filter_by(provider="outlook", provider_event_id=provider_event_id, external_account_id=external_account.id).first()
        start = it.get("start", {}).get("dateTime")
        end = it.get("end", {}).get("dateTime")
        if not mapping:
            ev = Event(user_id=external_account.user_id, title=it.get("subject") or "(no title)", description=it.get("bodyPreview"), start_at=datetime.fromisoformat(start.replace("Z", "+00:00")), end_at=datetime.fromisoformat(end.replace("Z", "+00:00")))
            db.session.add(ev)
            db.session.commit()
            mapping = ExternalEventMapping(provider="outlook", provider_event_id=provider_event_id, external_account_id=external_account.id, event_id=ev.id, last_synced_at=datetime.utcnow())
            db.session.add(mapping)
            db.session.commit()
            created += 1
    return created
