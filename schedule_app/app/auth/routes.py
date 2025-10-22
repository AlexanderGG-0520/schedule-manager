from __future__ import annotations
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from .. import db
from ..models import User
from ..forms import RegisterForm, LoginForm
from typing import cast
import smtplib
from email.message import EmailMessage
from sqlalchemy.exc import IntegrityError
import requests
from datetime import datetime, timedelta
from ..forms import ResendConfirmationForm
from flask import session
import pyotp

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


@auth_bp.route('/set-language', methods=['POST'])
def set_language():
    lang = request.form.get('lang')
    if lang in ('ja', 'en'):
        session['lang'] = lang
    return redirect(request.referrer or url_for('events.calendar'))


def send_email(subject: str, recipient: str, body: str, html: str | None = None) -> bool:
    provider = current_app.config.get("EMAIL_PROVIDER", "smtp")
    # Resend (API) provider
    if provider == "resend":
        try:
            api_key = current_app.config.get("RESEND_API_KEY")
            if not api_key:
                current_app.logger.error("RESEND_API_KEY not configured")
                return False
            payload = {
                "from": current_app.config.get("MAIL_DEFAULT_SENDER"),
                "to": [recipient],
                "subject": subject,
                "text": body,
            }
            if html:
                payload["html"] = html
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=10,
            )
            if resp.status_code in (200, 202):
                return True
            current_app.logger.error("Resend API returned non-success: %s %s", resp.status_code, resp.text)
            return False
        except Exception:
            current_app.logger.exception("Failed to send email via Resend API")
            return False

    # Fallback to SMTP if provider is not 'resend'
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = current_app.config.get("MAIL_DEFAULT_SENDER")
    msg["To"] = recipient
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
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
        current_app.logger.exception("Failed to send email via SMTP fallback")
        return False


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        existing = User.query.filter((User.username == form.username.data) | (User.email == form.email.data)).first()
        if existing:
            # If user exists and is not confirmed, offer to resend confirmation email instead of blocking silently
            if not existing.confirmed:
                # generate token for existing user and attempt resend
                token = existing.generate_confirmation_token()
                confirm_url = url_for("auth.confirm_email", token=token, _external=True)
                subject = "[Schedule Manager] メールアドレス確認 (再送)"
                body = f"以下のリンクをクリックして本登録を完了してください:\n\n{confirm_url}\n\nこのリンクは1時間で無効になります。"
                if send_email(subject, str(existing.email), body):
                    flash("確認メールを再送しました。受信トレイを確認してください。", "success")
                else:
                    flash("確認メールの送信に失敗しました。管理者に連絡してください。", "error")
                return render_template("auth/register.html", form=form)
            flash("ユーザー名またはメールアドレスは既に使用されています。", "warning")
            return render_template("auth/register.html", form=form)
        # Create user object in memory but do NOT persist until email is sent successfully
        user = User()
        user.username = form.username.data
        user.email = form.email.data
        user.set_password(cast(str, form.password.data))
        # marked unconfirmed until email verification
        user.confirmed = False

        # Generate token now (doesn't require DB persistence)
        token = user.generate_confirmation_token()
        confirm_url = url_for("auth.confirm_email", token=token, _external=True)
        subject = "[Schedule Manager] メールアドレス確認"
        body = f"以下のリンクをクリックして本登録を完了してください:\n\n{confirm_url}\n\nこのリンクは1時間で無効になります。"
        # Try sending email first. If it fails, do not persist the user.
        if not send_email(subject, str(user.email), body):
            flash("確認メールの送信に失敗しました。管理者に連絡してください。", "error")
            return render_template("auth/register.html", form=form)

        # Email sent successfully — now persist the user. Handle race conditions on unique constraints.
        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            current_app.logger.exception("User commit failed after email sent — possible race on unique constraint")
            flash("ユーザー名またはメールアドレスは既に使用されています。再度試してください。", "warning")
            return render_template("auth/register.html", form=form)

        flash("確認メールを送信しました。受信トレイを確認してください。", "success")
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


@auth_bp.route("/resend-confirmation", methods=["GET", "POST"])
def resend_confirmation():
    form = ResendConfirmationForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            flash("そのメールアドレスのアカウントは見つかりません。", "warning")
            return render_template("auth/resend_confirmation.html", form=form)
        if user.confirmed:
            flash("既に本登録済みです。ログインしてください。", "warning")
            return redirect(url_for("auth.login"))

        # rate-limit: 5 minutes default
        last = user.last_confirmation_sent_at
        now = datetime.utcnow()
        cooldown = timedelta(minutes=5)
        if last and now - last < cooldown:
            remaining = cooldown - (now - last)
            flash(f"確認メールは既に送信済みです。再送は{int(remaining.total_seconds()//60)}分後に行えます。", "info")
            return render_template("auth/resend_confirmation.html", form=form)

        token = user.generate_confirmation_token()
        confirm_url = url_for("auth.confirm_email", token=token, _external=True)
        subject = "[Schedule Manager] メールアドレス確認 (再送)"
        body = f"以下のリンクをクリックして本登録を完了してください:\n\n{confirm_url}\n\nこのリンクは1時間で無効になります。"
        if send_email(subject, str(user.email), body):
            user.last_confirmation_sent_at = db.func.now()
            db.session.add(user)
            db.session.commit()
            flash("確認メールを再送しました。受信トレイを確認してください。", "success")
            return redirect(url_for("auth.login"))
        else:
            flash("確認メールの送信に失敗しました。管理者に連絡してください。", "error")
    return render_template("auth/resend_confirmation.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            if not user.confirmed:
                flash("メールアドレスが未確認です。受信トレイの確認リンクをクリックしてください。", "warning")
                return redirect(url_for("auth.login"))
            # If 2FA is enabled, store pending login and prompt for TOTP
            if user.two_factor_enabled:
                session['pending_2fa_user'] = user.id
                # don't log in yet; redirect to 2FA verify form
                return redirect(url_for('auth.two_factor_verify'))
            login_user(user)
            # If there's a pending invite token saved in session, process it
            pending = session.pop("pending_invite", None)
            if pending:
                return redirect(url_for("organizations.accept_invite", token=pending))
            return redirect(url_for("events.calendar"))
        flash("認証に失敗しました。", "error")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route('/2fa/setup', methods=['GET'])
@login_required
def two_factor_setup():
    # generate or show secret for current user
    if not current_user.two_factor_secret:
        secret = pyotp.random_base32()
        current_user.two_factor_secret = secret
        db.session.add(current_user)
        db.session.commit()
    else:
        secret = current_user.two_factor_secret
    # provide provisioning URI for authenticator apps
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=current_user.email, issuer_name="ScheduleManager")
    # generate QR code as data URI
    try:
        import qrcode
        import io
        buf = io.BytesIO()
        img = qrcode.make(uri)
        img.save(buf, "PNG")
        data = buf.getvalue()
        import base64
        data_uri = 'data:image/png;base64,' + base64.b64encode(data).decode()
    except Exception:
        data_uri = None
    return render_template('auth/2fa_setup.html', secret=secret, uri=uri, qr_data_uri=data_uri)


@auth_bp.route('/2fa/backup', methods=['POST'])
@login_required
def two_factor_backup():
    # generate and show backup codes (plaintext only once)
    codes = current_user.generate_backup_codes()
    return render_template('auth/2fa_backup.html', codes=codes)


@auth_bp.route('/2fa/verify', methods=['GET', 'POST'])
def two_factor_verify():
    # Verify code from session-pending user during login or enablement flow
    user_id = session.get('pending_2fa_user')
    if not user_id:
        # maybe verifying from account settings for logged-in user
        if not current_user.is_authenticated:
            flash('2FAの確認に失敗しました。', 'error')
            return redirect(url_for('auth.login'))
        user = current_user
    else:
        user = User.query.get(user_id)
        if not user:
            flash('ログイン情報が見つかりません。', 'error')
            return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('code')
        totp = pyotp.TOTP(user.two_factor_secret or '')
        if code and totp.verify(code):
            # if coming from login flow, finalize login
            if session.get('pending_2fa_user'):
                session.pop('pending_2fa_user', None)
                login_user(user)
                return redirect(url_for('events.calendar'))
            # otherwise enable 2FA for current_user
            user.two_factor_enabled = True
            db.session.add(user)
            db.session.commit()
            flash('二要素認証を有効化しました。', 'success')
            return redirect(url_for('events.calendar'))
        else:
            flash('2FAコードが無効です。再試行してください。', 'error')
    return render_template('auth/2fa_verify.html')


@auth_bp.route('/2fa/disable', methods=['GET', 'POST'])
@login_required
def two_factor_disable():
    # Allow disabling 2FA by verifying current TOTP or a backup code
    if request.method == 'POST':
        code = request.form.get('code')
        password = request.form.get('password')
        # require password confirmation
        if not password or not current_user.check_password(password):
            flash('パスワードが正しくありません。無効化するにはパスワードで再認証してください。', 'error')
            return render_template('auth/2fa_disable.html')
        # TOTP verify first
        if current_user.two_factor_secret:
            totp = pyotp.TOTP(current_user.two_factor_secret)
            if code and totp.verify(code):
                # disable
                current_user.two_factor_enabled = False
                current_user.two_factor_secret = None
                current_user.two_factor_backup_codes = None
                db.session.add(current_user)
                db.session.commit()
                flash('二要素認証を無効にしました。', 'success')
                return redirect(url_for('events.calendar'))
        # try backup code
        if code and current_user.verify_and_consume_backup_code(code):
            current_user.two_factor_enabled = False
            current_user.two_factor_secret = None
            current_user.two_factor_backup_codes = None
            db.session.add(current_user)
            db.session.commit()
            flash('二要素認証を無効にしました（バックアップコード使用）。', 'success')
            return redirect(url_for('events.calendar'))
        flash('コードが無効です。', 'error')
    return render_template('auth/2fa_disable.html')
