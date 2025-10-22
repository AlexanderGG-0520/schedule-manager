from __future__ import annotations
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField
from wtforms.fields import DateTimeLocalField
from wtforms import SelectField
from wtforms.validators import DataRequired, Length, Email, Optional

class RegisterForm(FlaskForm):
    username = StringField("username", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("password", validators=[DataRequired(), Length(min=8)])

class LoginForm(FlaskForm):
    username = StringField("username", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("password", validators=[DataRequired()])

class EventForm(FlaskForm):
    title = StringField("title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("description", validators=[Optional(), Length(max=2000)])
    # DateTimeLocalField は input type="datetime-local" 用。保存時はUTCに変換すること。
    start_at = DateTimeLocalField("start_at", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    end_at = DateTimeLocalField("end_at", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    location = StringField("location", validators=[Optional(), Length(max=255)])
    participants = StringField("participants", validators=[Optional(), Length(max=2000)])
    category = StringField("category", validators=[Optional(), Length(max=64)])
    rrule = StringField("rrule", validators=[Optional(), Length(max=512)])
    timezone = StringField("timezone", validators=[Optional(), Length(max=64)])
    color = StringField("color", validators=[DataRequired(), Length(min=4, max=7)])
    organization_id = SelectField("organization_id", choices=[], coerce=int, validators=[Optional()])


class ResendConfirmationForm(FlaskForm):
    email = StringField("email", validators=[DataRequired(), Email(), Length(max=255)])


class OrganizationForm(FlaskForm):
    name = StringField("name", validators=[DataRequired(), Length(min=2, max=128)])


class InviteMemberForm(FlaskForm):
    username = StringField("username", validators=[DataRequired(), Length(min=3, max=80)])
