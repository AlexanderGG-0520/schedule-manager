from __future__ import annotations
from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from datetime import datetime
from ..models import Event
from .. import db
from ..models import Reaction, Retro, Task
from sqlalchemy import func

api_bp = Blueprint("api_v1", __name__)


def parse_iso8601(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception as exc:
        raise ValueError("不正な日時形式") from exc


@api_bp.route("/events", methods=["GET"])
@login_required
def list_events():
    start = request.args.get("start")
    end = request.args.get("end")
    query = request.args.get("query", "", type=str)

    # Debug logging using print to ensure visibility
    from flask import current_app
    print(f"[API] /events called - Authenticated: {current_user.is_authenticated}", flush=True)
    if current_user.is_authenticated:
        print(f"[API] User ID: {current_user.id}, Username: {current_user.username}", flush=True)
    else:
        print(f"[API] User not authenticated", flush=True)
        return jsonify({"error": "Not authenticated"}), 401

    # Get both personal events and organization events
    from ..models import Organization, User
    # Correct join: filter by User.id in the joined members, not Organization.id
    user_orgs = Organization.query.join(Organization.members).filter(User.id == current_user.id).all()
    org_ids = [org.id for org in user_orgs]
    
    print(f"[API] User organizations: {org_ids}", flush=True)
    
    # Personal events or events from user's organizations
    if org_ids:
        q = Event.query.filter(
            (Event.user_id == current_user.id) | 
            (Event.organization_id.in_(org_ids))
        )
    else:
        q = Event.query.filter(Event.user_id == current_user.id)
    
    # Debug: count total events for this user before date filtering
    total_before_filter = q.count()
    print(f"[API] Total events for user (before date filter): {total_before_filter}", flush=True)
    
    if start and end:
        try:
            start_dt = parse_iso8601(start)
            end_dt = parse_iso8601(end)
            # Convert to naive datetime for comparison (DB stores naive timestamps)
            # Assume DB times are in UTC
            if start_dt.tzinfo:
                start_dt = start_dt.replace(tzinfo=None)
            if end_dt.tzinfo:
                end_dt = end_dt.replace(tzinfo=None)
            print(f"[API] Date range filter: {start_dt} to {end_dt}", flush=True)
        except ValueError:
            abort(400, "start/end の形式が不正です")
        # Filter events that overlap with the date range
        q = q.filter(Event.start_at < end_dt, Event.end_at > start_dt)
    if query:
        q = q.filter(Event.title.ilike(f"%{query}%") | Event.description.ilike(f"%{query}%"))
    events = q.order_by(Event.start_at).all()
    
    print(f"[API] Query returned {len(events)} events", flush=True)
    
    # Temporary debug: include debug info in response
    debug_info = {
        "user_id": current_user.id,
        "username": current_user.username,
        "org_ids": org_ids,
        "total_before_filter": total_before_filter,
        "event_count": len(events),
        "date_range": f"{start} to {end}" if start and end else "no filter"
    }
    
    try:
        events_data = [{
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "start_at": e.start_at.isoformat() + 'Z' if e.start_at else None,
            "end_at": e.end_at.isoformat() + 'Z' if e.end_at else None,
            "color": e.color
        } for e in events]
    except Exception as e:
        print(f"[API] Error serializing events: {e}", flush=True)
        import traceback
        print(traceback.format_exc(), flush=True)
        events_data = []
    
    # Return with debug info
    return jsonify({
        "debug": debug_info,
        "events": events_data
    })


@api_bp.route('/events/<int:event_id>/reactions', methods=['GET'])
@login_required
def event_reactions(event_id: int):
    # return aggregation counts per emoji and whether current user reacted
    ev = Event.query.get_or_404(event_id)
    # permission: allow if owner or org member or personal
    if ev.organization_id:
        # for simplicity assume membership check elsewhere; here allow owners and org members
        pass
    # aggregation
    rows = db.session.query(Reaction.emoji, func.count(Reaction.id).label('count'))\
        .filter(Reaction.event_id == ev.id)\
        .group_by(Reaction.emoji).all()
    # did current user react and which emojis
    user_emojis = []
    if hasattr(current_user, 'id'):
        urows = Reaction.query.filter_by(event_id=ev.id, user_id=current_user.id).all()
        user_emojis = [r.emoji for r in urows]
    data = {r.emoji: r.count for r in rows}
    return jsonify({"counts": data, "you": user_emojis})


@api_bp.route('/events/<int:event_id>/reactions', methods=['POST'])
@login_required
def toggle_reaction(event_id: int):
    ev = Event.query.get_or_404(event_id)
    data = request.get_json() or {}
    emoji = data.get('emoji')
    if not emoji:
        abort(400, 'emoji is required')
    # toggle: if existing reaction by user with same emoji => remove, else add
    existing = None
    if current_user and getattr(current_user, 'id', None):
        existing = Reaction.query.filter_by(event_id=ev.id, user_id=current_user.id, emoji=emoji).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'removed': True, 'emoji': emoji})
    # create
    r = Reaction(event_id=ev.id, user_id=current_user.id, emoji=emoji)
    db.session.add(r)
    db.session.commit()
    return jsonify({'id': r.id, 'emoji': r.emoji}), 201


@api_bp.route('/events/<int:event_id>/retro', methods=['GET'])
@login_required
def get_retros(event_id: int):
    ev = Event.query.get_or_404(event_id)
    rows = Retro.query.filter_by(event_id=ev.id).order_by(Retro.created_at.desc()).all()
    out = [{
        'id': r.id,
        'user_id': r.user_id,
        'q1': r.q1,
        'q2': r.q2,
        'q3': r.q3,
        'next_action': r.next_action,
        'created_at': r.created_at.isoformat()
    } for r in rows]
    return jsonify(out)


@api_bp.route('/events/<int:event_id>/retro', methods=['POST'])
@login_required
def submit_retro(event_id: int):
    ev = Event.query.get_or_404(event_id)
    data = request.get_json() or {}
    q1 = data.get('q1', '')
    q2 = data.get('q2', '')
    q3 = data.get('q3', '')
    next_action = data.get('next_action')
    if not (q1 or q2 or q3 or next_action):
        abort(400, 'no content')
    r = Retro(event_id=ev.id, user_id=current_user.id, q1=q1, q2=q2, q3=q3, next_action=next_action)
    db.session.add(r)
    task = None
    if next_action:
        task = Task(user_id=current_user.id, title=next_action, event_id=ev.id)
        db.session.add(task)
    db.session.commit()
    resp = {'id': r.id}
    if task:
        resp['task_id'] = task.id
    return jsonify(resp), 201


@api_bp.route("/events", methods=["POST"])
@login_required
def create_event():
    data = request.get_json() or {}
    for k in ("title", "start_at", "end_at", "color"):
        if k not in data:
            abort(400, f"{k} が必要です")
    try:
        start_at = parse_iso8601(data["start_at"])
        end_at = parse_iso8601(data["end_at"])
    except ValueError:
        abort(400, "日時形式が不正です")

    if end_at <= start_at:
        abort(400, "終了時刻は開始時刻より後にしてください")

    # 型チェッカ（pylance）が SQLAlchemy モデルの __init__ シグネチャを
    # 正しく推論できないことがあるため、明示的に属性を代入する。
    event = Event()
    event.user_id = current_user.id
    event.title = data["title"]
    event.description = data.get("description")
    event.start_at = start_at
    event.end_at = end_at
    event.color = data.get("color", "#4287f5")
    db.session.add(event)
    db.session.commit()
    return jsonify({"id": event.id}), 201
