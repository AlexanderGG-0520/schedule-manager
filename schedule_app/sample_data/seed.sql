-- サンプルユーザーとイベント（パスワードはハッシュ化して挿入すること）
INSERT INTO users (id, username, email, password_hash, created_at)
VALUES (1, 'alice', 'alice@example.com', 'pbkdf2:sha256:150000$xxx$yyy', CURRENT_TIMESTAMP);

INSERT INTO events (user_id, title, description, start_at, end_at, color, created_at)
VALUES (1, 'ミーティング', 'プロジェクトミーティング', '2025-10-20 09:00:00', '2025-10-20 10:00:00', '#ff5722', CURRENT_TIMESTAMP);
