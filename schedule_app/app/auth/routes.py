from __future__ import annotations
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from .. import db
from ..models import User
from ..forms import RegisterForm, LoginForm
from typing import cast

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter((User.username == form.username.data) | (User.email == form.email.data)).first():
            flash("ユーザー名またはメールアドレスは既に使用されています。")
            return render_template("auth/register.html", form=form)
        # SQLAlchemy のモデルは __init__ のシグネチャが型チェッカで
        # 正しく推論されない場合があるため、属性を明示的に設定する。
        user = User()
        user.username = form.username.data
        user.email = form.email.data
        # 型チェッカ用に password を明示的に str にキャスト
        user.set_password(cast(str, form.password.data))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("events.calendar"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for("events.calendar"))
        flash("認証に失敗しました。")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
