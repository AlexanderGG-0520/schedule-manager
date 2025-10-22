from __future__ import annotations
import base64
import os
from cryptography.fernet import Fernet
from typing import Optional


def _get_fernet_key() -> bytes:
    key = os.getenv("INTEGRATIONS_ENCRYPTION_KEY")
    if key:
        # accept urlsafe base64 key or raw
        try:
            return key.encode()
        except Exception:
            pass
    # fallback: derive from SECRET_KEY (not ideal for production)
    secret = os.getenv("SECRET_KEY", "change-me-in-production").encode()
    # use base64 urlsafe to make a 32-byte key
    b = base64.urlsafe_b64encode(secret.ljust(32, b"0")[:32])
    return b


def encrypt_value(value: str) -> str:
    f = Fernet(_get_fernet_key())
    return f.encrypt(value.encode()).decode()


def decrypt_value(token: str) -> Optional[str]:
    try:
        f = Fernet(_get_fernet_key())
        return f.decrypt(token.encode()).decode()
    except Exception:
        return None
