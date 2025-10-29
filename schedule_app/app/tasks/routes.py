from __future__ import annotations
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from .. import db
from ..models import Task
from ..forms import TaskForm

tasks_bp = Blueprint("tasks", __name__, template_folder="../templates")


@tasks_bp.route("/tasks", methods=["GET"])
@login_required
def index():
    form = TaskForm()
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).all()
    return render_template("tasks/index.html", tasks=tasks, form=form)


@tasks_bp.route("/tasks/create", methods=["POST"])
@login_required
def create():
    form = TaskForm()
    if form.validate_on_submit():
        task = Task(user_id=current_user.id, title=form.title.data)
        db.session.add(task)
        db.session.commit()
        flash("タスクを追加しました。", "success")
    else:
        flash("タスクの追加に失敗しました。", "error")
    return redirect(url_for("tasks.index"))


@tasks_bp.route("/tasks/<int:task_id>/toggle", methods=["POST"])
@login_required
def toggle(task_id: int):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash("権限がありません。", "error")
        return redirect(url_for("tasks.index"))
    task.completed = not bool(task.completed)
    db.session.add(task)
    db.session.commit()
    return redirect(url_for("tasks.index"))


@tasks_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete(task_id: int):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash("権限がありません。", "error")
        return redirect(url_for("tasks.index"))
    db.session.delete(task)
    db.session.commit()
    flash("タスクを削除しました。", "success")
    return redirect(url_for("tasks.index"))
