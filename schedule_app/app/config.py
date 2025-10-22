import os
from typing import Final

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY: Final[str] = os.getenv("SECRET_KEY", "change-me-in-production")
    try:
        SQLALCHEMY_DATABASE_URI: Final[str] = os.environ["DATABASE_URL"]
    except KeyError:
        raise RuntimeError("DATABASE_URL environment variable is required (no sqlite fallback)")
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
    # Which email provider to use. Set to 'resend' to use Resend API (preferred), or 'smtp' to use SMTP.
    EMAIL_PROVIDER: Final[str] = os.getenv("EMAIL_PROVIDER", "smtp")
    # API key for Resend (when EMAIL_PROVIDER=resend). Kept empty by default so deployments without the key
    # continue to fall back to SMTP if desired.
    RESEND_API_KEY: Final[str] = os.getenv("RESEND_API_KEY", "")
    # Token settings for email confirmation
    SECURITY_PASSWORD_SALT: Final[str] = os.getenv("SECURITY_PASSWORD_SALT", "change-this-salt")
    CONFIRM_TOKEN_EXPIRATION: Final[int] = int(os.getenv("CONFIRM_TOKEN_EXPIRATION", "3600"))
    # Flask-WTF CSRF settings
    # Time limit for CSRF tokens (seconds). Increase if users report token expiry during form submission.
    # Set via env var `WTF_CSRF_TIME_LIMIT`. Use 0 or empty to disable time limit.
    WTF_CSRF_TIME_LIMIT: Final[int] = int(os.getenv("WTF_CSRF_TIME_LIMIT", "86400"))
    # Optional separate secret for CSRF signing. If not provided, SECRET_KEY is used.
    WTF_CSRF_SECRET_KEY: Final[str] = os.getenv("WTF_CSRF_SECRET_KEY", SECRET_KEY)
