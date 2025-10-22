import sys
import os
import pytest

# ensure repository root is on sys.path so `schedule_app` package can be imported
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Ensure tests have a DATABASE_URL so importing app.config doesn't raise
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
from schedule_app.app import create_app, db
from schedule_app.app.config import Config

# 親 Config が Final アノテーションを持つため、継承して属性を再宣言すると
# 型チェッカ（Pylance）で警告が出る。テスト用は独立クラスとして定義する。
class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    # 既存の Config から必要なら参照できるようにする
    SECRET_KEY = getattr(Config, "SECRET_KEY", "test-secret")

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()
