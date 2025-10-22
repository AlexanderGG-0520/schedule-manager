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
            start_at=form.start_at.data,
            end_at=form.end_at.data,
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
        event.start_at = form.start_at.data
        event.end_at = form.end_at.data
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
