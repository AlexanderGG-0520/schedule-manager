from __future__ import annotations
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField
from wtforms.fields import DateTimeLocalField
from wtforms import SelectField
from wtforms.validators import DataRequired, Length, Email, Optional, Regexp

class RegisterForm(FlaskForm):
    # username: allow ASCII letters, digits, underscore, hyphen and dot
    username = StringField(
        "username",
        validators=[
            DataRequired(),
            Length(min=3, max=80),
            Regexp(r"^[A-Za-z0-9_.-]+$", message="ユーザー名には英数字と _ . - のみ使用できます。"),
        ],
    )
    email = StringField("email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("password", validators=[DataRequired(), Length(min=8)])

class LoginForm(FlaskForm):
    username = StringField(
        "username",
        validators=[
            DataRequired(),
            Length(min=3, max=80),
            Regexp(r"^[A-Za-z0-9_.-]+$", message="ユーザー名には英数字と _ . - のみ使用できます。"),
        ],
    )
    password = PasswordField("password", validators=[DataRequired()])

# Common timezone choices for the EventForm
COMMON_TIMEZONES = [
    ('UTC', 'UTC'),
    ('Asia/Tokyo', 'Asia/Tokyo (日本)'),
    ('America/New_York', 'America/New_York (東部)'),
    ('America/Los_Angeles', 'America/Los_Angeles (太平洋)'),
    ('America/Chicago', 'America/Chicago (中部)'),
    ('Europe/London', 'Europe/London (英国)'),
    ('Europe/Paris', 'Europe/Paris (中欧)'),
    ('Australia/Sydney', 'Australia/Sydney (豪州)'),
    ('Asia/Shanghai', 'Asia/Shanghai (中国)'),
    ('Asia/Hong_Kong', 'Asia/Hong_Kong (香港)'),
    ('Asia/Singapore', 'Asia/Singapore (シンガポール)'),
    ('Asia/Seoul', 'Asia/Seoul (韓国)'),
]

class EventForm(FlaskForm):
    title = StringField("title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("description", validators=[Optional(), Length(max=2000)])
    # DateTimeLocalField は input type="datetime-local" 用。ユーザーの選択したタイムゾーンで解釈してUTCに変換する
    start_at = DateTimeLocalField("start_at", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    end_at = DateTimeLocalField("end_at", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    location = StringField("location", validators=[Optional(), Length(max=255)])
    participants = StringField("participants", validators=[Optional(), Length(max=2000)])
    category = StringField("category", validators=[Optional(), Length(max=64)])
    rrule = StringField("rrule", validators=[Optional(), Length(max=512)])
    timezone = SelectField("timezone", choices=COMMON_TIMEZONES, validators=[DataRequired()], default='Asia/Tokyo')
    color = StringField("color", validators=[DataRequired(), Length(min=4, max=7)])
    organization_id = SelectField("organization_id", choices=[], coerce=int, validators=[Optional()])


class ResendConfirmationForm(FlaskForm):
    email = StringField("email", validators=[DataRequired(), Email(), Length(max=255)])


class ResetPasswordForm(FlaskForm):
    password = PasswordField("password", validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField("confirm", validators=[DataRequired(), Length(min=8)])


class OrganizationForm(FlaskForm):
    name = StringField("name", validators=[DataRequired(), Length(min=2, max=128)])


class InviteMemberForm(FlaskForm):
    username = StringField(
        "username",
        validators=[
            DataRequired(),
            Length(min=3, max=80),
            Regexp(r"^[A-Za-z0-9_.-@]+$", message="ユーザー名/メールには英数字と @ _ . - のみ使用できます。"),
        ],
    )


class TaskForm(FlaskForm):
    title = StringField("title", validators=[DataRequired(), Length(min=1, max=255)])


class ResetUsernameForm(FlaskForm):
    new_username = StringField(
        "new_username",
        validators=[
            DataRequired(),
            Length(min=3, max=80),
            Regexp(r"^[A-Za-z0-9_.-]+$", message="ユーザー名には英数字と _ . - のみ使用できます。"),
        ],
    )
