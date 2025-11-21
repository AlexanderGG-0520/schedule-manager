from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from .config import Config
from flask_babel import Babel

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
babel = Babel()

def create_app(config=None):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config or Config)
    
    # Configure logging
    import logging
    app.logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)

    # If using a file-based SQLite URI, ensure the parent directory exists so the DB file can be created.
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if db_uri and db_uri.startswith("sqlite:") and "///" in db_uri:
        # format: sqlite:////absolute/path or sqlite:///relative/path
        path_part = db_uri.split("///", 1)[1]
        # For absolute paths there may be a leading slash; normalize
        from pathlib import Path
        db_path = Path(path_part)
        parent = db_path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            # If we can't create the directory, log via app.logger later when context is available
            pass

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
    babel.init_app(app)

    def get_locale():
        # allow user override via session, else Accept-Language
        from flask import session, request
        if session.get('lang'):
            return session.get('lang')
        return request.accept_languages.best_match(['ja', 'en'])

    # Register the locale selector function (assign to attribute to satisfy type checkers)
    try:
        # Preferred for modern Flask-Babel versions
        babel.locale_selector_func = get_locale  # type: ignore[attr-defined]
    except Exception:
        # Fallback for older Flask-Babel versions that only have the decorator API
        try:
            babel.localeselector(get_locale)  # type: ignore[attr-defined]
        except Exception:
            pass

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
    from .organizations.routes import org_bp
    from .api.v1 import api_bp
    # Integrations (optional) - register each integrations blueprint if its module is importable
    try:
        from .integrations.routes import integrations_bp

        app.register_blueprint(integrations_bp)
    except Exception:
        # integrations routes are optional
        pass

    try:
        from .integrations.google import google_bp

        app.register_blueprint(google_bp)
    except Exception:
        # google integration optional
        pass

    try:
        from .integrations.outlook import outlook_bp

        app.register_blueprint(outlook_bp)
    except Exception:
        # outlook integration optional
        pass

    app.register_blueprint(auth_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(org_bp)
    # Exempt API blueprint from CSRF protection (uses session auth still)
    csrf.exempt(api_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    # Tasks (ToDo) blueprint
    try:
        from .tasks.routes import tasks_bp

        app.register_blueprint(tasks_bp)
    except Exception:
        # If tasks blueprint import fails, continue silently
        pass

    # Register CLI commands (scheduler)
    try:
        from .cli import scheduler_cli

        app.cli.add_command(scheduler_cli)
    except Exception:
        # If importing the CLI fails (e.g., missing optional deps), continue silently
        pass

    return app
