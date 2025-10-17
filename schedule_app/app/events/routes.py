from __future__ import annotations
from flask import Blueprint, render_template
from flask_login import login_required

events_bp = Blueprint("events", __name__, template_folder="../templates")


@events_bp.route("/")
@login_required
def calendar():
    # カレンダービュー（フロント側で API と連携）
    return render_template("calendar.html")
