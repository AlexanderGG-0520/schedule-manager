from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from .config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config=None):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config or Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    # 未認証時のリダイレクト先と flash カテゴリを設定
    login_manager.login_view = "auth.login"  # type: ignore
    login_manager.login_message_category = "warning"  # type: ignore
    # Flask-Login: ユーザーIDから User インスタンスを復元するローダーを登録
    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            # User.id は整数なので、文字列を int に変換して検索
            return User.query.get(int(user_id))
        except Exception:
            return None
    csrf.init_app(app)

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    # ヘルスチェックエンドポイント: Kubernetes の readiness/liveness probe 用
    @app.route("/health", methods=["GET"])
    def health_check():
        # 簡易的に 200 を返す。将来的に DB などの依存チェックを追加しても良い。
        return ("OK", 200)

    from .auth.routes import auth_bp
    from .events.routes import events_bp
    from .api.v1 import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    return app
