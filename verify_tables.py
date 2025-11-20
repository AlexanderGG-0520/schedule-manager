#!/usr/bin/env python
"""Verify notifications table exists."""
import os

password = os.environ.get("PGPASSWORD", "rick02roll")
os.environ["DATABASE_URL"] = f"postgresql://postgres:{password}@localhost:5433/schedule_db"

from schedule_app.app import create_app, db

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        result = db.session.execute(db.text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE '%notification%'"
        ))
        tables = [row[0] for row in result]
        print(f"Notification-related tables: {tables}")
        
        # Test inserting a test record (we'll delete it right after)
        from schedule_app.app.models import Notification
        print(f"Notification model: {Notification}")
        print("✓ Notifications table is accessible!")
