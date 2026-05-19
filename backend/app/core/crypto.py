import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class CryptoError(Exception):
    pass


def _settings():
    return get_settings()


def _fernet() -> Fernet:
    s = _settings()
    if not s.token_encryption_key:
        raise CryptoError("TOKEN_ENCRYPTION_KEY not configured")
    try:
        return Fernet(s.token_encryption_key.encode())
    except Exception as e:
        raise CryptoError(f"invalid TOKEN_ENCRYPTION_KEY: {e.__class__.__name__}") from e


def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise CryptoError("invalid encrypted token") from e


def issue_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    s = _settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.jwt_access_ttl_minutes)).timestamp()),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, s.secret_key, algorithm=s.jwt_algorithm)


def verify_access_token(token: str) -> dict[str, Any]:
    s = _settings()
    try:
        payload = jwt.decode(token, s.secret_key, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError as e:
        raise CryptoError(f"invalid token: {e.__class__.__name__}") from e
    if payload.get("type") != "access":
        raise CryptoError("not an access token")
    return payload


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def refresh_expiry() -> datetime:
    s = _settings()
    return datetime.now(UTC) + timedelta(days=s.jwt_refresh_ttl_days)


def generate_csrf_state() -> str:
    return secrets.token_urlsafe(32)


def constant_time_eq(a: str, b: str) -> bool:
    return secrets.compare_digest(a, b)
