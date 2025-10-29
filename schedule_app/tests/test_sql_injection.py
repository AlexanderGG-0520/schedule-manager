def test_login_resists_sql_injection(client):
    # Register a normal user first
    rv = client.post('/register', data={
        'username': 'sqltester', 'email': 'sql@example.com', 'password': 'safePass123'
    }, follow_redirects=True)
    assert rv.status_code == 200

    # Attempt SQL injection in username field
    payload = "' OR '1'='1"
    rv = client.post('/login', data={'username': payload, 'password': 'doesnotmatter'}, follow_redirects=True)
    # Login should fail and flash an authentication failure message
    assert "認証に失敗しました".encode('utf-8') in rv.data

    # Ensure correct credentials still work
    rv = client.post('/login', data={'username': 'sqltester', 'password': 'safePass123'}, follow_redirects=True)
    assert rv.status_code == 200
