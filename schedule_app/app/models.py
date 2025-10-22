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
    # track when the last confirmation email was sent to allow rate-limiting resends
    last_confirmation_sent_at = db.Column(db.DateTime, nullable=True)

    events = db.relationship("Event", back_populates="user", cascade="all, delete-orphan")
    # organizations the user belongs to (many-to-many)
    organizations = db.relationship(
        "Organization",
        secondary="organization_members",
        back_populates="members",
    )

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
    # Optional organization the event belongs to (shared within organization)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    organization = db.relationship("Organization", back_populates="events")


class Organization(db.Model):
    __tablename__ = "organizations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Members relationship via association table
    members = db.relationship(
        "User",
        secondary="organization_members",
        back_populates="organizations",
    )

    events = db.relationship("Event", back_populates="organization", cascade="all, delete-orphan")


# Association table for organization memberships with role
class OrganizationMember(db.Model):
    __tablename__ = "organization_members"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), primary_key=True)
    role = db.Column(db.String(20), nullable=False, default="member")  # member or admin
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Invitation(db.Model):
    __tablename__ = "invitations"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    invited_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="member")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    accepted = db.Column(db.Boolean, default=False, nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=True)

    organization = db.relationship("Organization", backref="invitations")
