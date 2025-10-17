import pytest
from app import create_app, db
from app.config import Config

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
