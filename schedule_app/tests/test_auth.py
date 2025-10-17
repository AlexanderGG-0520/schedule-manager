def test_register_and_login(client):
    rv = client.post('/register', data={
        'username': 'tester', 'email': 't@example.com', 'password': 'secret123'
    }, follow_redirects=True)
    assert rv.status_code == 200

    rv = client.post('/login', data={'username': 'tester', 'password': 'secret123'}, follow_redirects=True)
    assert rv.status_code == 200
