-- Create notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    method VARCHAR(32) NOT NULL,
    scheduled_at TIMESTAMP NOT NULL,
    sent BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_notifications_event_id ON notifications (event_id);
CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id);
CREATE INDEX IF NOT EXISTS ix_notifications_scheduled_at ON notifications (scheduled_at);

-- Create event_participants table
CREATE TABLE IF NOT EXISTS event_participants (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL,
    user_id INTEGER,
    email VARCHAR(255),
    status VARCHAR(20) NOT NULL,
    role VARCHAR(32) NOT NULL,
    invited_at TIMESTAMP NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_event_participants_event_id ON event_participants (event_id);
CREATE INDEX IF NOT EXISTS ix_event_participants_user_id ON event_participants (user_id);
CREATE INDEX IF NOT EXISTS ix_event_participants_email ON event_participants (email);

-- Create event_comments table
CREATE TABLE IF NOT EXISTS event_comments (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_event_comments_event_id ON event_comments (event_id);

-- Update alembic_version to mark this migration as applied
INSERT INTO alembic_version (version_num) VALUES ('0012')
ON CONFLICT (version_num) DO NOTHING;
