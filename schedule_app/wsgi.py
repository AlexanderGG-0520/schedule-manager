from __future__ import annotations

# WSGI エントリポイント: gunicorn が 'wsgi:app' を読み込めるように
# `create_app()` を正しいモジュールから取得してアプリケーションインスタンスを生成し、
# それを `app` として公開する。
#
# `create_app` は `schedule_app/app/__init__.py` に定義されているため
# 明示的に `schedule_app.app` からインポートする。
from schedule_app.app import create_app


app = create_app()
