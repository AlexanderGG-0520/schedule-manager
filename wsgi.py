from __future__ import annotations

# Top-level WSGI entry so `gunicorn wsgi:app` works when repository root is PYTHONPATH
# It delegates to schedule_app.create_app()
from schedule_app import create_app

app = create_app()
