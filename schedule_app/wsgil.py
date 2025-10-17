# wsgi.py - Flask ファクトリ create_app() を呼ぶ簡易 WSGI エントリポイント
from app import create_app

# Gunicorn はこの 'app' を探して WSGI callable として使います
app = create_app()