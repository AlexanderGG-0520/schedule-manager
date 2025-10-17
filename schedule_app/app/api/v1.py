from __future__ import annotations
from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from datetime import datetime
from ..models import Event
from .. import db

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

    q = Event.query.filter(Event.user_id == current_user.id)
    if start and end:
        try:
            start_dt = parse_iso8601(start)
            end_dt = parse_iso8601(end)
        except ValueError:
            abort(400, "start/end の形式が不正です")
        q = q.filter(Event.start_at >= start_dt, Event.end_at <= end_dt)
    if query:
        q = q.filter(Event.title.ilike(f"%{query}%") | Event.description.ilike(f"%{query}%"))
    events = q.order_by(Event.start_at).all()
    return jsonify([{
        "id": e.id,
        "title": e.title,
        "description": e.description,
        "start_at": e.start_at.isoformat(),
        "end_at": e.end_at.isoformat(),
        "color": e.color
    } for e in events])


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
