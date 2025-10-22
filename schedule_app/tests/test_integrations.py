import json
from schedule_app.app import db
from schedule_app.app.models import User, ExternalAccount, IntegrationLog
import pytest
from datetime import datetime, timedelta

def login(client, email='test@example.com'):
    # create user and set session
    from schedule_app.app.models import User
    # construct user without passing unexpected constructor kwargs, then assign attributes
    user = User()
    user.email = email
    user.password_hash = 'x'
    user.name = 'test'
    db.session.add(user)
    db.session.commit()
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
    return user

    with app.app_context():
        user = User(email='u@example.com', password_hash='x')
        user.name = 'u'
        db.session.add(user)
        db.session.commit()
        acc = ExternalAccount(user_id=user.id, provider='google', external_id='ext-1')
        db.session.add(acc)
        db.session.commit()
        db.session.add(acc)
        db.session.commit()
        # add a couple logs
        l1 = IntegrationLog(provider='google', account_id=acc.id, level='info', message='ok')
        l2 = IntegrationLog(provider='google', account_id=acc.id, level='error', message='bad')
        db.session.add_all([l1, l2])
        db.session.commit()
        # fake login by setting Flask-Login session key
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
        resp = client.get(f'/integrations/accounts/{acc.id}/history')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'items' in data
        assert data['total'] == 2
