import time
import uuid

import jwt
import pytest

from app.config import get_settings
from app.core.crypto import (
    CryptoError,
    decrypt_token,
    encrypt_token,
    issue_access_token,
    verify_access_token,
)


def test_should_roundtrip_when_fernet_token_encrypted():
    plain = "ghp_secret_value_abc"
    ct = encrypt_token(plain)
    assert ct != plain
    assert decrypt_token(ct) == plain


def test_should_reject_when_fernet_token_tampered():
    ct = encrypt_token("plain")
    bad = ct[:-2] + ("aa" if ct[-2:] != "aa" else "bb")
    with pytest.raises(CryptoError):
        decrypt_token(bad)


def test_should_roundtrip_when_access_token_issued():
    sub = str(uuid.uuid4())
    tok = issue_access_token(sub, {"login": "alice"})
    payload = verify_access_token(tok)
    assert payload["sub"] == sub
    assert payload["login"] == "alice"
    assert payload["type"] == "access"


def test_should_reject_when_token_signature_wrong():
    sub = str(uuid.uuid4())
    tok = issue_access_token(sub)
    parts = tok.split(".")
    forged = ".".join(parts[:2] + ["AAAA"])
    with pytest.raises(CryptoError):
        verify_access_token(forged)


def test_should_reject_when_token_expired():
    s = get_settings()
    now = int(time.time())
    expired = jwt.encode(
        {"sub": "x", "iat": now - 3600, "exp": now - 1, "type": "access"},
        s.secret_key,
        algorithm=s.jwt_algorithm,
    )
    with pytest.raises(CryptoError):
        verify_access_token(expired)


def test_should_reject_when_token_type_wrong():
    s = get_settings()
    now = int(time.time())
    bad = jwt.encode(
        {"sub": "x", "iat": now, "exp": now + 60, "type": "refresh"},
        s.secret_key,
        algorithm=s.jwt_algorithm,
    )
    with pytest.raises(CryptoError):
        verify_access_token(bad)
