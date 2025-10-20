from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db
from itsdangerous import URLSafeTimedSerializer
from flask import current_app
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    confirmed = db.Column(db.Boolean, default=False, nullable=False)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    events = db.relationship("Event", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self) -> str:
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        return serializer.dumps(self.email, salt=current_app.config.get("SECURITY_PASSWORD_SALT"))

    @staticmethod
    def confirm_token(token: str, expiration: "int | None" = None) -> "str | None":
        expiration = expiration or current_app.config.get("CONFIRM_TOKEN_EXPIRATION", 3600)
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        try:
            email = serializer.loads(token, salt=current_app.config.get("SECURITY_PASSWORD_SALT"), max_age=expiration)
        except Exception:
            return None
        return email


class Event(db.Model):
    __tablename__ = "events"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_at = db.Column(db.DateTime, nullable=False, index=True)
    end_at = db.Column(db.DateTime, nullable=False, index=True)
    color = db.Column(db.String(7), nullable=False, default="#4287f5")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="events")
