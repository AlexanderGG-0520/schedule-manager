from __future__ import annotations

# WSGI エントリポイント: gunicorn が 'wsgi:app' を読み込めるように
# create_app() でアプリケーションインスタンスを生成して 'app' として公開する
from app import create_app

app = create_app()
