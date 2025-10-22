from __future__ import annotations
from flask import Blueprint, render_template
from flask_login import login_required

events_bp = Blueprint("events", __name__, template_folder="../templates")


@events_bp.route("/")
@login_required
def calendar():
    # カレンダービュー（フロント側で API と連携）
    return render_template("calendar.html")


from flask import request, redirect, url_for, flash, current_app
from ..models import Event, Organization, OrganizationMember, User
from .. import db
from ..forms import EventForm
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from typing import cast, Any
from ..models import User as UserModel
from datetime import datetime, timedelta
from flask import jsonify
from dateutil.rrule import rrulestr
from dateutil import tz as dateutil_tz
from dateutil.tz import tzutc
from typing import Optional
from werkzeug.utils import secure_filename
import os
from ..models import EventParticipant, EventComment, Attachment
from itsdangerous import URLSafeTimedSerializer
from flask import session
from ..auth.routes import send_email


def user_is_org_admin(user: User, org: Organization) -> bool:
    mem = db.session.query(OrganizationMember).filter_by(user_id=user.id, organization_id=org.id).first()
    return bool(mem and mem.role == "admin")


@events_bp.route("/events")
@login_required
def list_events():
    org_id = request.args.get("org_id", type=int)
    if org_id:
        org = Organization.query.get_or_404(org_id)
        # ensure current_user is member
        if current_user not in org.members:
            flash("この組織のイベントを表示する権限がありません。", "error")
            return redirect(url_for("events.calendar"))
        events = Event.query.filter_by(organization_id=org_id).order_by(Event.start_at).all()
    else:
        # personal events
        events = Event.query.filter_by(user_id=current_user.id, organization_id=None).order_by(Event.start_at).all()
    return render_template("events/list.html", events=events)



@events_bp.route("/api/v1/events")
@login_required
def api_events():
    """Return events as JSON for a given time window.

    Query params:
      - start: ISO datetime (inclusive)
      - end: ISO datetime (exclusive)
      - org_id: optional organization id to filter
    """
    start_s = request.args.get("start")
    end_s = request.args.get("end")
    org_id = request.args.get("org_id", type=int)

    def parse_iso(s: str | None) -> Optional[datetime]:
        """Parse an ISO datetime string into a timezone-aware datetime in UTC.

        Accepts inputs like '2025-10-22T12:00:00Z' or '2025-10-22T12:00:00+09:00'.
        If the input has no tzinfo, it's assumed to be in UTC.
        Returns a datetime with tzinfo=tzutc().
        """
        if not s:
            return None
        try:
            # datetime.fromisoformat supports offsets like +09:00
            if s.endswith("Z"):
                # replace trailing Z with +00:00 for fromisoformat compatibility
                s2 = s[:-1] + "+00:00"
            else:
                s2 = s
            dt = datetime.fromisoformat(s2)
            if dt.tzinfo is None:
                # assume naive timestamps are UTC
                return dt.replace(tzinfo=tzutc())
            # normalize to UTC
            return dt.astimezone(tzutc())
        except Exception:
            return None

    start_dt = parse_iso(start_s)
    end_dt = parse_iso(end_s)

    q = Event.query
    if org_id:
        org = Organization.query.get_or_404(org_id)
        if current_user not in org.members:
            return jsonify([]), 403
        q = q.filter_by(organization_id=org_id)
    else:
        q = q.filter_by(user_id=current_user.id, organization_id=None)

    # Convert query window to UTC naive datetimes for comparison against stored DB values
    # Assumption: Event.start_at / end_at are stored in UTC (naive) in DB.
    if start_dt and end_dt:
        # convert to naive UTC for DB comparison
        start_naive = start_dt.astimezone(tzutc()).replace(tzinfo=None)
        end_naive = end_dt.astimezone(tzutc()).replace(tzinfo=None)
        # overlapping events: start < end_dt and end > start_dt
        q = q.filter(Event.start_at < end_naive, Event.end_at > start_naive)
    events = q.order_by(Event.start_at).all()

    def to_iso(dt: datetime | None) -> Optional[str]:
        if not dt:
            return None
        # ensure we return an UTC ISO string with Z
        if dt.tzinfo is None:
            # assume stored as UTC naive
            return dt.replace(tzinfo=tzutc()).isoformat().replace('+00:00', 'Z')
        return dt.astimezone(tzutc()).isoformat().replace('+00:00', 'Z')

    out = []
    for e in events:
        if e.rrule:
            # try to parse rrule and expand occurrences within window
            try:
                # rrule string expected without DTSTART; use event start as DTSTART.
                # Use the event's timezone if available so occurrences are generated in that zone.
                tzname = e.timezone or "UTC"
                try:
                    event_tz = dateutil_tz.gettz(tzname) or tzutc()
                except Exception:
                    event_tz = tzutc()

                # make dtstart tz-aware in event timezone
                dtstart = e.start_at
                if dtstart is None:
                    dtstart = datetime.utcnow()
                # if stored as naive UTC assume UTC and convert to event timezone
                if dtstart.tzinfo is None:
                    dtstart = dtstart.replace(tzinfo=tzutc()).astimezone(event_tz)
                else:
                    dtstart = dtstart.astimezone(event_tz)

                rule = rrulestr(e.rrule, dtstart=dtstart)
                # get occurrences in [start_dt, end_dt) — convert window to event tz for comparison
                if start_dt and end_dt:
                    window_start = start_dt.astimezone(event_tz)
                    window_end = end_dt.astimezone(event_tz)
                    occs = list(rule.between(window_start, window_end, inc=True))
                else:
                    # limit to next 50 occurrences if no window provided
                    occs = list(rule[:50])
                for occ in occs:
                    # occ is in event_tz; calculate duration from original event (normalize end/start)
                    # convert original start/end to event_tz
                    start_orig = e.start_at
                    end_orig = e.end_at
                    if start_orig.tzinfo is None:
                        start_orig = start_orig.replace(tzinfo=tzutc()).astimezone(event_tz)
                    else:
                        start_orig = start_orig.astimezone(event_tz)
                    if end_orig.tzinfo is None:
                        end_orig = end_orig.replace(tzinfo=tzutc()).astimezone(event_tz)
                    else:
                        end_orig = end_orig.astimezone(event_tz)
                    duration = end_orig - start_orig
                    occ_end = occ + duration
                    # convert occurrence times back to UTC for API output
                    occ_utc = occ.astimezone(tzutc())
                    occ_end_utc = occ_end.astimezone(tzutc())
                    out.append({
                        "id": e.id,
                        "title": e.title,
                        "start": to_iso(occ_utc),
                        "end": to_iso(occ_end_utc),
                        "color": e.color,
                        "organization_id": e.organization_id,
                        "original_start": to_iso(e.start_at),
                        "location": e.location,
                        "participants": e.participants,
                        "category": e.category,
                        "timezone": e.timezone,
                    })
                continue
            except Exception:
                current_app.logger.exception("RRULE parse/expand failed for event %s", e.id)
        # non-recurring or failed to expand
        out.append(
            {
                "id": e.id,
                "title": e.title,
                "start": to_iso(e.start_at),
                "end": to_iso(e.end_at),
                "color": e.color,
                "organization_id": e.organization_id,
                "location": e.location,
                "participants": e.participants,
                "category": e.category,
                "timezone": e.timezone,
            }
        )
    return jsonify(out)


@events_bp.route("/events/create", methods=["GET", "POST"])
@login_required
def create_event():
    form = EventForm()
    # populate organization choices with memberships (use the real user object)
    current_user_obj = cast(UserModel, current_user._get_current_object())
    orgs = getattr(current_user_obj, "organizations", []) or []
    # WTForms SelectField expects string values for option values; convert ids to str
    choices = [(str(-1), "個人用")] + [(str(o.id), o.name) for o in orgs]
    form.organization_id.choices = cast(Any, choices)

    if form.validate_on_submit():
        org_id_raw = form.organization_id.data
        try:
            org_id = int(org_id_raw) if org_id_raw is not None else None
        except (TypeError, ValueError):
            org_id = None
        if org_id == -1:
            org_id = None
        else:
            # ensure membership
            org = Organization.query.get(org_id)
            if not org or current_user_obj not in org.members:
                flash("組織に対する権限がありません。", "error")
                return render_template("events/create.html", form=form)
        event = Event(
            user_id=current_user.id,
            title=form.title.data,
            description=form.description.data,
            location=form.location.data,
            participants=form.participants.data,
            start_at=form.start_at.data,
            end_at=form.end_at.data,
            category=form.category.data,
            rrule=form.rrule.data,
            timezone=form.timezone.data,
            color=form.color.data,
            organization_id=org_id,
        )
        try:
            db.session.add(event)
            db.session.commit()
            flash("イベントを作成しました。", "success")
            return redirect(url_for("events.list_events") + (f"?org_id={org_id}" if org_id else ""))
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("イベント作成中に DB エラー")
            flash("イベントの作成に失敗しました。", "error")
    return render_template("events/create.html", form=form)


@events_bp.route("/events/<int:event_id>/invite", methods=["POST"])
@login_required
def invite_participant(event_id: int):
    event = Event.query.get_or_404(event_id)
    email = request.form.get("email")
    role = request.form.get("role", "participant")
    # permission: only owner or org admin can invite
    current_user_obj = cast(UserModel, current_user._get_current_object())
    allowed = False
    if event.user_id == current_user_obj.id:
        allowed = True
    elif event.organization_id and current_user_obj in event.organization.members:
        if user_is_org_admin(current_user_obj, event.organization):
            allowed = True
    if not allowed:
        return jsonify({"error": "permission denied"}), 403
    if not email:
        return jsonify({"error": "missing email"}), 400

    # create participant record
    p = EventParticipant(event_id=event.id, email=email, role=role, status="pending")
    db.session.add(p)
    db.session.commit()

    # generate token for invitation acceptance
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    token = serializer.dumps({"participant_id": p.id, "event_id": event.id}, salt=current_app.config.get("SECURITY_PASSWORD_SALT"))
    accept_url = url_for("events.accept_invite", token=token, _external=True)
    subject = f"[{current_app.config.get('APP_NAME','Schedule Manager')}] イベント招待: {event.title}"
    # Render templates
    text_body = render_template("emails/invite.txt", inviter_name=current_user_obj.username, recipient_name=None, event=event, accept_url=accept_url)
    html_body = render_template("emails/invite.html", inviter_name=current_user_obj.username, recipient_name=None, event=event, accept_url=accept_url)
    # send email (best-effort)
    try:
        sent = send_email(subject, str(email), text_body, html=html_body)
        if sent:
            flash(f"招待メールを {email} に送信しました。", "success")
            return jsonify({"id": p.id, "email": p.email, "status": p.status}), 201
        else:
            current_app.logger.error("Failed to send invite email to %s", email)
            flash("招待メールの送信に失敗しました。後で再試行してください。", "error")
            return jsonify({"id": p.id, "email": p.email, "status": p.status, "warning": "mail_failed"}), 202
    except Exception:
        current_app.logger.exception("Error while sending invite email to %s", email)
        flash("招待メールの送信に失敗しました。管理者に連絡してください。", "error")
        return jsonify({"id": p.id, "email": p.email, "status": p.status, "error": "mail_exception"}), 500



@events_bp.route("/events/invite/accept/<token>")
def accept_invite(token: str):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    data = None
    try:
        data = serializer.loads(token, salt=current_app.config.get("SECURITY_PASSWORD_SALT"), max_age=24 * 3600)
    except Exception:
        flash("招待リンクが無効か期限切れです。", "error")
        return redirect(url_for("auth.login"))
    participant_id = data.get("participant_id")
    event_id = data.get("event_id")
    p = EventParticipant.query.get(participant_id)
    if not p or p.event_id != event_id:
        flash("招待が見つかりません。", "error")
        return redirect(url_for("auth.login"))
    # If user is not authenticated, save token to session and redirect to login
    if not current_user.is_authenticated:
        session["pending_invite"] = token
        flash("参加するにはログインしてください。ログイン後に招待が処理されます。", "info")
        return redirect(url_for("auth.login"))
    # At this point user is authenticated
    current_user_obj = cast(UserModel, current_user._get_current_object())
    # Only allow the invited email/user to accept
    if p.user_id and p.user_id != current_user_obj.id:
        flash("この招待を承認する権限がありません。", "error")
        return redirect(url_for("events.calendar"))
    if p.email and p.email.lower() != current_user_obj.email.lower() and p.user_id is None:
        flash("招待メールのアドレスとログインユーザーが一致しません。", "error")
        return redirect(url_for("events.calendar"))
    p.status = "accepted"
    p.user_id = current_user_obj.id
    db.session.add(p)
    db.session.commit()
    flash("イベントへの参加を承認しました。", "success")
    return redirect(url_for("events.list_events") + (f"?org_id={p.event.organization_id}" if p.event.organization_id else ""))


@events_bp.route("/events/<int:event_id>/participants/<int:participant_id>/respond", methods=["POST"])
@login_required
def respond_participation(event_id: int, participant_id: int):
    p = EventParticipant.query.get_or_404(participant_id)
    if p.event_id != event_id:
        return jsonify({"error": "mismatch"}), 400
    # Allow either the invited user (by email match) or the logged-in user
    current_user_obj = cast(UserModel, current_user._get_current_object())
    action = request.form.get("action")  # 'accept' or 'decline'
    if p.user_id and p.user_id != current_user_obj.id:
        return jsonify({"error": "permission denied"}), 403
    # If p.user_id is null, allow if emails match
    if not p.user_id and p.email and p.email.lower() != current_user_obj.email.lower():
        return jsonify({"error": "permission denied"}), 403
    if action == "accept":
        p.status = "accepted"
    else:
        p.status = "declined"
    if not p.user_id:
        p.user_id = current_user_obj.id
    db.session.add(p)
    db.session.commit()
    return jsonify({"id": p.id, "status": p.status})


@events_bp.route("/events/<int:event_id>/comments", methods=["GET", "POST"])
@login_required
def comments(event_id: int):
    event = Event.query.get_or_404(event_id)
    if request.method == "GET":
        data = [
            {"id": c.id, "user_id": c.user_id, "content": c.content, "parent_id": c.parent_id, "created_at": c.created_at.isoformat()}
            for c in event.comments
        ]
        return jsonify(data)
    # POST
    content = request.form.get("content")
    parent_id = request.form.get("parent_id", type=int)
    current_user_obj = cast(UserModel, current_user._get_current_object())
    c = EventComment(event_id=event.id, user_id=current_user_obj.id, content=content, parent_id=parent_id)
    db.session.add(c)
    db.session.commit()
    return jsonify({"id": c.id, "content": c.content, "created_at": c.created_at.isoformat()}), 201


UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@events_bp.route("/events/<int:event_id>/attachments", methods=["GET", "POST"])
@login_required
def attachments(event_id: int):
    event = Event.query.get_or_404(event_id)
    if request.method == "GET":
        return jsonify([
            {"id": a.id, "filename": a.filename, "content_type": a.content_type, "uploaded_at": a.uploaded_at.isoformat()}
            for a in event.attachments
        ])
    # POST - upload
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400
    f = request.files["file"]
    raw_filename = f.filename or ""
    filename = secure_filename(raw_filename)
    if not filename:
        return jsonify({"error": "invalid filename"}), 400
    storage_name = f"{datetime.utcnow().timestamp()}_{filename}"
    storage_path = os.path.join(UPLOAD_DIR, storage_name)
    f.save(storage_path)
    current_user_obj = cast(UserModel, current_user._get_current_object())
    a = Attachment(event_id=event.id, filename=filename, content_type=f.content_type, storage_path=storage_path, uploaded_by=current_user_obj.id)
    db.session.add(a)
    db.session.commit()
    return jsonify({"id": a.id, "filename": a.filename}), 201


@events_bp.route("/events/<int:event_id>/freebusy")
@login_required
def freebusy(event_id: int):
    """Return a simple free/busy view for event participants.

    For each participant (EventParticipant) return their busy windows overlapping the event window.
    This is a minimal implementation for candidate time calculations.
    """
    event = Event.query.get_or_404(event_id)
    # gather participants as emails or users
    parts = []
    for p in getattr(event, "participants_assoc", []):
        if p.user_id:
            u = User.query.get(p.user_id)
            parts.append({"id": u.id, "email": u.email})
        else:
            parts.append({"id": None, "email": p.email})
    # For each participant, collect events overlapping the same window
    window_start = event.start_at
    window_end = event.end_at
    result = []
    for person in parts:
        if person["id"]:
            other_events = Event.query.filter(Event.user_id == person["id"], Event.start_at < window_end, Event.end_at > window_start).all()
            busy = [{"start": e.start_at.isoformat(), "end": e.end_at.isoformat(), "title": e.title} for e in other_events]
        else:
            busy = []
        result.append({"participant": person, "busy": busy})
    return jsonify({"event": event.id, "participants": result})


@events_bp.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
def edit_event(event_id: int):
    event = Event.query.get_or_404(event_id)
    # permission check
    current_user_obj = cast(UserModel, current_user._get_current_object())
    if event.organization_id:
        org = event.organization
        # allow if owner, or member with admin role
        if current_user_obj.id == event.user_id:
            allowed = True
        else:
            allowed = False
            if current_user_obj in org.members:
                # check if admin
                if user_is_org_admin(current_user_obj, org):
                    allowed = True
        if not allowed:
            flash("イベントを編集する権限がありません。", "error")
            return redirect(url_for("events.calendar"))
    else:
        if event.user_id != current_user_obj.id:
            flash("イベントを編集する権限がありません。", "error")
            return redirect(url_for("events.calendar"))

    form = EventForm(obj=event)
    orgs = getattr(current_user_obj, "organizations", []) or []
    choices = [(str(-1), "個人用")] + [(str(o.id), o.name) for o in orgs]
    form.organization_id.choices = cast(Any, choices)
    form.organization_id.data = event.organization_id or -1

    if form.validate_on_submit():
        org_id_raw = form.organization_id.data
        try:
            org_id = int(org_id_raw) if org_id_raw is not None else None
        except (TypeError, ValueError):
            org_id = None
        if org_id == -1:
            org_id = None
        else:
            org = Organization.query.get(org_id)
            if not org or current_user_obj not in org.members:
                flash("組織に対する権限がありません。", "error")
                return render_template("events/edit.html", form=form, event=event)
        event.title = form.title.data
        event.description = form.description.data
        event.location = form.location.data
        event.participants = form.participants.data
        event.start_at = form.start_at.data
        event.end_at = form.end_at.data
        event.category = form.category.data
        event.rrule = form.rrule.data
        event.timezone = form.timezone.data
        event.color = form.color.data
        event.organization_id = org_id
        try:
            db.session.add(event)
            db.session.commit()
            flash("イベントを更新しました。", "success")
            return redirect(url_for("events.list_events") + (f"?org_id={org_id}" if org_id else ""))
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("イベント更新中に DB エラー")
            flash("イベントの更新に失敗しました。", "error")
    return render_template("events/edit.html", form=form, event=event)


@events_bp.route("/events/<int:event_id>/delete", methods=["POST"])
@login_required
def delete_event(event_id: int):
    event = Event.query.get_or_404(event_id)
    # permission: owner or org admin
    current_user_obj = cast(UserModel, current_user._get_current_object())
    if event.organization_id:
        org = event.organization
        # owner or org admin can delete
        if current_user_obj.id != event.user_id and not user_is_org_admin(current_user_obj, org):
            flash("イベントを削除する権限がありません。", "error")
            return redirect(url_for("events.calendar"))
    else:
        if event.user_id != current_user_obj.id:
            flash("イベントを削除する権限がありません。", "error")
            return redirect(url_for("events.calendar"))
    try:
        db.session.delete(event)
        db.session.commit()
        flash("イベントを削除しました。", "success")
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("イベント削除中に DB エラー")
        flash("イベントの削除に失敗しました。", "error")
    return redirect(url_for("events.calendar"))
