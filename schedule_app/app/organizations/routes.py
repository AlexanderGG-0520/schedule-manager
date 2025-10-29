from __future__ import annotations
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_required, current_user
from ..forms import OrganizationForm, InviteMemberForm
from .. import db
from ..models import Organization, OrganizationMember, User
from ..models import Invitation
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy.exc import SQLAlchemyError
from ..auth.routes import send_email
from typing import cast
from ..models import User as UserModel

org_bp = Blueprint("organizations", __name__, template_folder="../templates")


@org_bp.route("/orgs")
@login_required
def list_orgs():
    orgs = current_user.organizations
    return render_template("organizations/list.html", orgs=orgs)


@org_bp.route("/orgs/create", methods=["GET", "POST"])
@login_required
def create_org():
    form = OrganizationForm()
    if form.validate_on_submit():
        # Prevent duplicate organization names with a pre-check to give a friendly message
        existing_org = Organization.query.filter_by(name=form.name.data).first()
        if existing_org:
            flash("同じ名前の組織が既に存在します。別の名前を選択してください。", "warning")
            return render_template("organizations/create.html", form=form)

        org = Organization(name=form.name.data, owner_id=current_user.id)
        try:
            db.session.add(org)
            db.session.flush()
            # add membership for owner as admin
            mem = OrganizationMember(user_id=current_user.id, organization_id=org.id, role="admin")
            db.session.add(mem)
            db.session.commit()
            flash("組織を作成しました。", "success")
            return redirect(url_for("organizations.list_orgs"))
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("組織作成中に DB エラー")
            flash("組織の作成に失敗しました。", "error")
    return render_template("organizations/create.html", form=form)


@org_bp.route("/orgs/<int:org_id>")
@login_required
def view_org(org_id: int):
    org = Organization.query.get_or_404(org_id)
    if current_user not in org.members:
        flash("この組織を見る権限がありません。", "error")
        return redirect(url_for("organizations.list_orgs"))
    invite_form = InviteMemberForm()
    return render_template("organizations/view.html", org=org, invite_form=invite_form)



@org_bp.route("/orgs/<int:org_id>/invite", methods=["POST"])
@login_required
def invite_member(org_id: int):
    org = Organization.query.get_or_404(org_id)
    if current_user not in org.members:
        flash("この組織に対する権限がありません。", "error")
        return redirect(url_for("organizations.list_orgs"))
    form = InviteMemberForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if not user:
            # Create an email invitation record and send email with token
            email = str(form.username.data)
            # If the input looks like an email address, validate its format before attempting to send
            if "@" in email:
                from wtforms.validators import Email as WTEmail
                from wtforms.form import Form as WTForm
                from wtforms import StringField
                try:
                    # Use a WTForms Email validator instance to perform a lightweight validation
                    dummy_form = WTForm()
                    dummy_field = StringField("email")
                    dummy_field.data = email
                    WTEmail()(dummy_form, dummy_field)
                except Exception:
                    flash("無効なメールアドレス形式です。正しいメールアドレスを入力してください。", "error")
                    return redirect(url_for("organizations.view_org", org_id=org.id))

            inv = Invitation(email=email, organization_id=org.id, invited_by=current_user.id, role="member")
            try:
                db.session.add(inv)
                db.session.commit()
                # generate token
                serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
                token = serializer.dumps({"inv_id": inv.id}, salt=current_app.config.get("SECURITY_PASSWORD_SALT"))
                accept_url = url_for("organizations.accept_invite", token=token, _external=True)
                subject = f"{org.name} への招待"
                body = f"{org.name} への参加招待を受け取りました。以下のリンクをクリックして参加してください:\n\n{accept_url}\n\nこのリンクは1時間で無効になります。"
                send_email(subject, str(email), body)
                flash("招待メールを送信しました。受信トレイを確認してください。", "success")
            except SQLAlchemyError:
                db.session.rollback()
                current_app.logger.exception("招待レコード作成中に DB エラー")
                flash("招待に失敗しました。", "error")
            return redirect(url_for("organizations.view_org", org_id=org.id))
        # add membership if not exists
        existing = OrganizationMember.query.filter_by(user_id=user.id, organization_id=org.id).first()
        if existing:
            flash("ユーザーは既に組織のメンバーです。", "info")
            return redirect(url_for("organizations.view_org", org_id=org.id))
        try:
            mem = OrganizationMember(user_id=user.id, organization_id=org.id, role="member")
            db.session.add(mem)
            db.session.commit()
            flash("ユーザーを招待しました。", "success")
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("招待中に DB エラー")
            flash("招待に失敗しました。", "error")
    return redirect(url_for("organizations.view_org", org_id=org.id))



@org_bp.route("/orgs/<int:org_id>/members/<int:user_id>/remove", methods=["POST"])
@login_required
def remove_member(org_id: int, user_id: int):
    org = Organization.query.get_or_404(org_id)
    # require that current_user is a member and has admin role (or is owner)
    my_membership = OrganizationMember.query.filter_by(user_id=current_user.id, organization_id=org.id).first()
    if not my_membership:
        flash("この組織に対する権限がありません。", "error")
        return redirect(url_for("organizations.list_orgs"))
    if my_membership.role != "admin" and org.owner_id != current_user.id:
        flash("メンバーの削除権限がありません。", "error")
        return redirect(url_for("organizations.view_org", org_id=org.id))

    # prevent removing the owner
    if user_id == org.owner_id:
        flash("オーナーは削除できません。", "error")
        return redirect(url_for("organizations.view_org", org_id=org.id))

    membership = OrganizationMember.query.filter_by(user_id=user_id, organization_id=org.id).first()
    if not membership:
        flash("対象ユーザーはメンバーではありません。", "info")
        return redirect(url_for("organizations.view_org", org_id=org.id))
    try:
        db.session.delete(membership)
        db.session.commit()
        flash("メンバーを削除しました。", "success")
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("メンバー削除中に DB エラー")
        flash("メンバーの削除に失敗しました。", "error")
    return redirect(url_for("organizations.view_org", org_id=org.id))



@org_bp.route("/orgs/invite/accept/<token>")
def accept_invite(token: str):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        data = serializer.loads(token, salt=current_app.config.get("SECURITY_PASSWORD_SALT"), max_age=3600)
    except SignatureExpired:
        flash("招待リンクの有効期限が切れています。", "error")
        return redirect(url_for("auth.login"))
    except BadSignature:
        flash("無効な招待リンクです。", "error")
        return redirect(url_for("auth.login"))
    inv_id = data.get("inv_id")
    inv = Invitation.query.get_or_404(inv_id)
    # If the user is logged in, associate; else ask to login/register
    if not current_user.is_authenticated:
        # store token in session so login flow can process it later
        session["pending_invite"] = token
        # render a friendly landing page explaining the invite and next steps
        try:
            org = Organization.query.get(inv.organization_id)
        except Exception:
            org = None
        # resolve inviter username for friendlier display
        inviter = None
        try:
            inviter = User.query.get(inv.invited_by)
        except Exception:
            inviter = None
        inviter_name = inviter.username if inviter else None
        inviter_email = inviter.email if inviter else None
        return render_template(
            "organizations/accept_landing.html", org=org, inviter_username=inviter_name, inviter_email=inviter_email
        )
    user_obj = cast(UserModel, current_user._get_current_object())
    # create membership if not exists
    existing = OrganizationMember.query.filter_by(user_id=user_obj.id, organization_id=inv.organization_id).first()
    if existing:
        flash("既に組織のメンバーです。", "info")
        return redirect(url_for("organizations.view_org", org_id=inv.organization_id))
    try:
        mem = OrganizationMember(user_id=user_obj.id, organization_id=inv.organization_id, role=inv.role)
        inv.accepted = True
        inv.accepted_at = db.func.now()
        db.session.add(mem)
        db.session.add(inv)
        db.session.commit()
        flash("組織に参加しました。", "success")
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("招待受諾中に DB エラー")
        flash("招待の処理に失敗しました。", "error")
    return redirect(url_for("organizations.view_org", org_id=inv.organization_id))
