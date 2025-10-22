import os
from typing import Final

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY: Final[str] = os.getenv("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI: Final[str] = os.getenv(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, '..', 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: Final[bool] = False
    SESSION_COOKIE_HTTPONLY: Final[bool] = True
    SESSION_COOKIE_SECURE: Final[bool] = os.getenv("FLASK_ENV") == "production"
    SESSION_COOKIE_SAMESITE: Final[str] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    REMEMBER_COOKIE_HTTPONLY: Final[bool] = True
    REMEMBER_COOKIE_SECURE: Final[bool] = os.getenv("FLASK_ENV") == "production"
    # Mail settings (for confirmation emails)
    MAIL_SERVER: Final[str] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT: Final[int] = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS: Final[bool] = bool(os.getenv("MAIL_USE_TLS", "True") == "True")
    MAIL_USERNAME: Final[str] = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD: Final[str] = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER: Final[str] = os.getenv("MAIL_DEFAULT_SENDER", "no-reply@aivis-chan-bot.com")
    # Token settings for email confirmation
    SECURITY_PASSWORD_SALT: Final[str] = os.getenv("SECURITY_PASSWORD_SALT", "change-this-salt")
    CONFIRM_TOKEN_EXPIRATION: Final[int] = int(os.getenv("CONFIRM_TOKEN_EXPIRATION", "3600"))
    # Flask-WTF CSRF settings
    # Time limit for CSRF tokens (seconds). Increase if users report token expiry during form submission.
    # Set via env var `WTF_CSRF_TIME_LIMIT`. Use 0 or empty to disable time limit.
    WTF_CSRF_TIME_LIMIT: Final[int] = int(os.getenv("WTF_CSRF_TIME_LIMIT", "86400"))
    # Optional separate secret for CSRF signing. If not provided, SECRET_KEY is used.
    WTF_CSRF_SECRET_KEY: Final[str] = os.getenv("WTF_CSRF_SECRET_KEY", SECRET_KEY)
