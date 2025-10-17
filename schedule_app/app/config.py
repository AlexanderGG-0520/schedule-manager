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
    REMEMBER_COOKIE_HTTPONLY: Final[bool] = True
