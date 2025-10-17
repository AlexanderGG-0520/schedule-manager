from __future__ import annotations

# Top-level WSGI entry so `gunicorn wsgi:app` works when repository root is PYTHONPATH
# This delegates to the factory in `schedule_app.app.create_app` which is the
# authoritative place for application setup.
from schedule_app.app import create_app


app = create_app()
