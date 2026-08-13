"""Encryption helpers for sensitive secrets stored at rest (e.g. API keys).

Keys are encrypted with Fernet, with the key derived from the app's JWT secret.
If that secret is rotated, previously encrypted values can no longer be
decrypted and users must re-enter their API keys.
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.JWT_SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        # Plaintext legacy value (written before encryption); return as-is so
        # existing settings keep working until the next save re-encrypts them.
        return value
