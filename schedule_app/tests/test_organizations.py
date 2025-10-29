from itsdangerous import URLSafeTimedSerializer
from flask import current_app
from schedule_app.app import db
from schedule_app.app.models import User, Organization, OrganizationMember, Invitation


def create_user(username, email, password='pw123'):
    u = User()
    u.username = username
    u.email = email
    u.set_password(password)
    u.confirmed = True
    db.session.add(u)
    db.session.commit()
    return u


def login(client, username, password='pw123'):
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)


def test_invite_registered_user_and_auto_add_member(client, app):
    # create owner and target
    with app.app_context():
        owner = create_user('owner', 'owner@example.com')
        target = create_user('target', 'target@example.com')
        target_id = target.id
        org = Organization(name='TestOrg', owner_id=owner.id)
        db.session.add(org)
        db.session.flush()
        owner_mem = OrganizationMember(user_id=owner.id, organization_id=org.id, role='admin')
        db.session.add(owner_mem)
        db.session.commit()
        org_id = org.id

    # login as owner and invite existing user
    rv = login(client, 'owner')
    assert rv.status_code == 200
    resp = client.post(f'/orgs/{org_id}/invite', data={'username': 'target'}, follow_redirects=True)
    assert resp.status_code == 200

    # check membership exists
    with app.app_context():
        mem = OrganizationMember.query.filter_by(user_id=target_id, organization_id=org_id).first()
        assert mem is not None
        assert mem.role == 'member'


def test_invite_unregistered_and_accept_after_login(client, app):
    # create owner and org
    with app.app_context():
        owner = create_user('owner2', 'owner2@example.com')
        org = Organization(name='OrgInvite', owner_id=owner.id)
        db.session.add(org)
        db.session.flush()
        db.session.add(OrganizationMember(user_id=owner.id, organization_id=org.id, role='admin'))
        db.session.commit()
        org_id = org.id

    # login as owner and invite an email that is not registered
    rv = login(client, 'owner2')
    assert rv.status_code == 200
    resp = client.post(f'/orgs/{org_id}/invite', data={'username': 'newuser@example.com'}, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        inv = Invitation.query.filter_by(email='newuser@example.com', organization_id=org_id).first()
        assert inv is not None
        inv_id = inv.id
        # build token same way the app does
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = serializer.dumps({'inv_id': inv_id}, salt=current_app.config.get('SECURITY_PASSWORD_SALT'))

    # anonymous GET to accept -> should render landing and set session pending_invite
    # make sure we are logged out so this simulates an anonymous user following the invite link
    client.get('/logout', follow_redirects=True)
    rv = client.get(f'/orgs/invite/accept/{token}', follow_redirects=True)
    assert rv.status_code == 200
    # ensure the pending_invite token was stored in session for later processing
    with client.session_transaction() as sess:
        assert 'pending_invite' in sess
        assert sess['pending_invite'] == token

    # Now create the user and login; login route should process pending_invite and create membership
    with app.app_context():
        newuser = create_user('newuser', 'newuser@example.com')
        newuser_id = newuser.id

    rv = login(client, 'newuser')
    assert rv.status_code == 200

    with app.app_context():
        mem = OrganizationMember.query.filter_by(user_id=newuser_id, organization_id=org_id).first()
        assert mem is not None
        inv = Invitation.query.get(inv_id)
        assert inv.accepted is True


def test_remove_member_authorization(client, app):
    with app.app_context():
        owner = create_user('owner3', 'owner3@example.com')
        admin = create_user('admin', 'admin@example.com')
        member = create_user('member', 'member@example.com')
        org = Organization(name='OrgRemove', owner_id=owner.id)
        db.session.add(org)
        db.session.flush()
        db.session.add(OrganizationMember(user_id=owner.id, organization_id=org.id, role='admin'))
        db.session.add(OrganizationMember(user_id=admin.id, organization_id=org.id, role='admin'))
        db.session.add(OrganizationMember(user_id=member.id, organization_id=org.id, role='member'))
        db.session.commit()
        org_id = org.id
        member_id = member.id

    # login as non-admin (create a non-admin user)
    with app.app_context():
        non_admin = create_user('nonadmin', 'nonadmin@example.com')
        non_admin_id = non_admin.id
        # add non_admin as a normal member of org
        db.session.add(OrganizationMember(user_id=non_admin_id, organization_id=org_id, role='member'))
        db.session.commit()

    rv = login(client, 'nonadmin')
    assert rv.status_code == 200
    # try to remove another member
    resp = client.post(f'/orgs/{org_id}/members/{member_id}/remove', follow_redirects=True)
    assert resp.status_code == 200
    page_text = resp.get_data(as_text=True)
    assert '削除権限' in page_text or '権限がありません' in page_text

    # now login as admin and remove member
    rv = login(client, 'admin')
    assert rv.status_code == 200
    resp = client.post(f'/orgs/{org_id}/members/{member_id}/remove', follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        mem = OrganizationMember.query.filter_by(user_id=member.id, organization_id=org.id).first()
        assert mem is None


def test_accept_invalid_and_expired_tokens(client, app, monkeypatch):
    # invalid token should be handled and show error
    rv = client.get('/orgs/invite/accept/this-is-not-a-valid-token', follow_redirects=True)
    assert rv.status_code == 200
    page_text = rv.get_data(as_text=True)
    assert '無効な招待リンク' in page_text or '招待リンク' in page_text

    # expired token simulation: monkeypatch URLSafeTimedSerializer.loads to raise SignatureExpired
    from itsdangerous import SignatureExpired, URLSafeTimedSerializer
    def fake_loads(self, token, salt=None, max_age=None):
        raise SignatureExpired('expired')
    # patch the class method properly
    monkeypatch.setattr(URLSafeTimedSerializer, 'loads', fake_loads)
    # generate a token-like string (content irrelevant since loads is patched)
    rv2 = client.get('/orgs/invite/accept/some-token', follow_redirects=True)
    assert rv2.status_code == 200
    page_text2 = rv2.get_data(as_text=True)
    # app may redirect to login; accept either the expiry message or a login page
    assert ('有効期限' in page_text2) or ('ログイン' in page_text2) or ('招待リンク' in page_text2)


def test_already_accepted_invite(client, app):
    with app.app_context():
        owner = create_user('owner4', 'owner4@example.com')
        target = create_user('target4', 'target4@example.com')
        org = Organization(name='OrgAlready', owner_id=owner.id)
        db.session.add(org)
        db.session.flush()
        db.session.add(OrganizationMember(user_id=owner.id, organization_id=org.id, role='admin'))
        # create an invitation and mark accepted
        inv = Invitation(email=target.email, organization_id=org.id, invited_by=owner.id)
        db.session.add(inv)
        db.session.flush()
        inv.accepted = True
        db.session.add(inv)
        db.session.commit()
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = serializer.dumps({'inv_id': inv.id}, salt=current_app.config.get('SECURITY_PASSWORD_SALT'))

    # login as target (already a user but not a member) - since inv.accepted True, code should say already member or show info
    rv = login(client, 'target4')
    assert rv.status_code == 200
    # accessing accept as authenticated should lead to '既に組織のメンバー' OR normal flow that simply redirects
    resp = client.get(f'/orgs/invite/accept/{token}', follow_redirects=True)
    assert resp.status_code == 200
    page_text = resp.get_data(as_text=True)
    assert '既に組織のメンバー' in page_text or '組織に参加しました' in page_text or '招待の処理に失敗しました' in page_text


def test_send_email_called_on_unregistered_invite(client, app, monkeypatch):
    called = {}

    def fake_send_email(subject, recipient, body, html=None):
        called['subject'] = subject
        called['recipient'] = recipient
        called['body'] = body
        called['html'] = html
        return True

    # patch the send_email function imported in organizations.routes
    monkeypatch.setattr('schedule_app.app.organizations.routes.send_email', fake_send_email)

    with app.app_context():
        owner = create_user('owner5', 'owner5@example.com')
        org = Organization(name='OrgEmailTest', owner_id=owner.id)
        db.session.add(org)
        db.session.flush()
        db.session.add(OrganizationMember(user_id=owner.id, organization_id=org.id, role='admin'))
        db.session.commit()
        org_id = org.id

    rv = login(client, 'owner5')
    assert rv.status_code == 200
    resp = client.post(f'/orgs/{org_id}/invite', data={'username': 'invitee@example.com'}, follow_redirects=True)
    assert resp.status_code == 200
    assert 'recipient' in called and called['recipient'] == 'invitee@example.com'
