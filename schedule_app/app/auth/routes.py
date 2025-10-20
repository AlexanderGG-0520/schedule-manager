from __future__ import annotations
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from .. import db
from ..models import User
from ..forms import RegisterForm, LoginForm
from typing import cast
import smtplib
from email.message import EmailMessage

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


def send_email(subject: str, recipient: str, body: str) -> bool:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = current_app.config.get("MAIL_DEFAULT_SENDER")
    msg["To"] = recipient
    msg.set_content(body)
    try:
        mail_server: str = str(current_app.config.get("MAIL_SERVER"))
        mail_port: int = int(current_app.config.get("MAIL_PORT") or 0)
        server = smtplib.SMTP(mail_server, mail_port)
        if bool(current_app.config.get("MAIL_USE_TLS")):
            server.starttls()
        username = str(current_app.config.get("MAIL_USERNAME") or "")
        password = str(current_app.config.get("MAIL_PASSWORD") or "")
        if username and password:
            server.login(username, password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        current_app.logger.exception("Failed to send email")
        return False


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter((User.username == form.username.data) | (User.email == form.email.data)).first():
            flash("ユーザー名またはメールアドレスは既に使用されています。", "warning")
            return render_template("auth/register.html", form=form)
        user = User()
        user.username = form.username.data
        user.email = form.email.data
        user.set_password(cast(str, form.password.data))
        # marked unconfirmed until email verification
        user.confirmed = False
        db.session.add(user)
        db.session.commit()

        token = user.generate_confirmation_token()
        confirm_url = url_for("auth.confirm_email", token=token, _external=True)
        subject = "[Schedule Manager] メールアドレス確認"
        body = f"以下のリンクをクリックして本登録を完了してください:\n\n{confirm_url}\n\nこのリンクは1時間で無効になります。"

        if send_email(subject, str(user.email), body):
            flash("確認メールを送信しました。受信トレイを確認してください。", "success")
        else:
            flash("確認メールの送信に失敗しました。管理者に連絡してください。", "error")

        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/confirm/<token>")
def confirm_email(token: str):
    email = User.confirm_token(token)
    if not email:
        flash("確認リンクが無効または期限切れです。", "error")
        return redirect(url_for("auth.login"))
    user = User.query.filter_by(email=email).first()
    if not user:
        flash("ユーザーが見つかりません。", "error")
        return redirect(url_for("auth.register"))
    if user.confirmed:
        flash("既に本登録済みです。", "warning")
        return redirect(url_for("auth.login"))
    user.confirmed = True
    user.confirmed_at = db.func.now()
    db.session.add(user)
    db.session.commit()
    flash("メールアドレスを確認しました。ログインしてください。", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            if not user.confirmed:
                flash("メールアドレスが未確認です。受信トレイの確認リンクをクリックしてください。", "warning")
                return redirect(url_for("auth.login"))
            login_user(user)
            return redirect(url_for("events.calendar"))
        flash("認証に失敗しました。", "error")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
