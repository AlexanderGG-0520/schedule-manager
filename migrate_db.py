#!/usr/bin/env python
"""Script to manually create the notifications table."""
import os
import sys

# Get password from environment or use default
password = os.environ.get("PGPASSWORD", "rick02roll")
os.environ["DATABASE_URL"] = f"postgresql://postgres:{password}@localhost:5433/schedule_db"

from schedule_app.app import create_app, db

SQL_COMMANDS = [
    """CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY,
        event_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        method VARCHAR(32) NOT NULL,
        scheduled_at TIMESTAMP NOT NULL,
        sent BOOLEAN NOT NULL,
        created_at TIMESTAMP NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    );""",
    "CREATE INDEX IF NOT EXISTS ix_notifications_event_id ON notifications (event_id);",
    "CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_notifications_scheduled_at ON notifications (scheduled_at);",
    """CREATE TABLE IF NOT EXISTS event_participants (
        id SERIAL PRIMARY KEY,
        event_id INTEGER NOT NULL,
        user_id INTEGER,
        email VARCHAR(255),
        status VARCHAR(20) NOT NULL,
        role VARCHAR(32) NOT NULL,
        invited_at TIMESTAMP NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    );""",
    "CREATE INDEX IF NOT EXISTS ix_event_participants_event_id ON event_participants (event_id);",
    "CREATE INDEX IF NOT EXISTS ix_event_participants_user_id ON event_participants (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_event_participants_email ON event_participants (email);",
    """CREATE TABLE IF NOT EXISTS event_comments (
        id SERIAL PRIMARY KEY,
        event_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    );""",
    "CREATE INDEX IF NOT EXISTS ix_event_comments_event_id ON event_comments (event_id);",
    "INSERT INTO alembic_version (version_num) VALUES ('0012') ON CONFLICT (version_num) DO NOTHING;"
]

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print("Creating notifications, event_participants, and event_comments tables...")
        try:
            for i, cmd in enumerate(SQL_COMMANDS, 1):
                print(f"Executing SQL command {i}/{len(SQL_COMMANDS)}...")
                db.session.execute(db.text(cmd))
                db.session.commit()
            print("✓ Tables created successfully!")
        except Exception as e:
            print(f"✗ Error creating tables: {e}")
            db.session.rollback()
            raise
