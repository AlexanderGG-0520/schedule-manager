def test_login_resists_sql_injection(client):
    # Register a normal user first
    rv = client.post('/register', data={
        'username': 'sqltester', 'email': 'sql@example.com', 'password': 'safePass123'
    }, follow_redirects=True)
    assert rv.status_code == 200

    # Attempt SQL injection in username field
    payload = "' OR '1'='1"
    rv = client.post('/login', data={'username': payload, 'password': 'doesnotmatter'}, follow_redirects=True)
    # Login should fail and not set a logged-in session
    with client.session_transaction() as sess:
        assert '_user_id' not in sess

    # Ensure correct credentials still work
    rv = client.post('/login', data={'username': 'sqltester', 'password': 'safePass123'}, follow_redirects=True)
    assert rv.status_code == 200
