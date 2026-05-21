"""BYOK endpoint tests.

The real upstream call to Anthropic is monkeypatched at the import seam
in `app.api.routes.user_api_keys` so tests never burn real API tokens.
"""
import pytest

from app.core.crypto import issue_access_token
from app.models.user import User
from app.services.user_api_key import ValidationResult


@pytest.fixture
async def alice(db) -> User:
    u = User(github_user_id=1001, github_login="alice")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def bob(db) -> User:
    u = User(github_user_id=2002, github_login="bob")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


def _auth(client, user: User) -> None:
    client.cookies.update(
        {"basira_access": issue_access_token(str(user.id), {"login": user.github_login})}
    )


def _patch_validator(monkeypatch, *, valid: bool, error: str | None = None) -> None:
    async def fake_validate(api_key: str) -> ValidationResult:
        return ValidationResult(valid=valid, error=error)

    monkeypatch.setattr(
        "app.api.routes.user_api_keys.validate_anthropic_key", fake_validate
    )


async def test_put_valid_key_returns_200_with_last_four(
    client, db, monkeypatch, alice
):
    _patch_validator(monkeypatch, valid=True)
    _auth(client, alice)
    r = await client.put(
        "/api/me/api-keys/anthropic",
        json={"api_key": "sk-ant-fake-key-with-suffix-WXYZ"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "anthropic"
    assert body["key_last_four"] == "WXYZ"
    assert body["is_valid"] is True
    assert body["last_validated_at"] is not None


async def test_put_invalid_key_returns_400(client, db, monkeypatch, alice):
    _patch_validator(monkeypatch, valid=False, error="key was rejected by anthropic")
    _auth(client, alice)
    r = await client.put(
        "/api/me/api-keys/anthropic",
        json={"api_key": "sk-ant-totally-bogus-key-1234"},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "INVALID_API_KEY"
    list_r = await client.get("/api/me/api-keys")
    assert list_r.json() == []


async def test_get_without_auth_returns_401(client, db, monkeypatch, alice):
    r = await client.get("/api/me/api-keys")
    assert r.status_code == 401


async def test_user_b_cannot_see_user_a_key(client, db, monkeypatch, alice, bob):
    _patch_validator(monkeypatch, valid=True)
    _auth(client, alice)
    r = await client.put(
        "/api/me/api-keys/anthropic",
        json={"api_key": "sk-ant-alice-key-secret-ABCD"},
    )
    assert r.status_code == 200

    _auth(client, bob)
    r = await client.get("/api/me/api-keys")
    assert r.status_code == 200
    assert r.json() == []


async def test_delete_then_get_returns_empty(client, db, monkeypatch, alice):
    _patch_validator(monkeypatch, valid=True)
    _auth(client, alice)
    await client.put(
        "/api/me/api-keys/anthropic",
        json={"api_key": "sk-ant-some-key-9999"},
    )
    r = await client.get("/api/me/api-keys")
    assert len(r.json()) == 1

    r = await client.delete("/api/me/api-keys/anthropic")
    assert r.status_code == 204

    r = await client.get("/api/me/api-keys")
    assert r.json() == []


async def test_get_user_anthropic_key_roundtrip(db, monkeypatch, alice):
    """Service-level roundtrip: encrypt on PUT, decrypt via
    get_user_anthropic_key. The scan engine relies on this returning the
    original plaintext."""
    from app.services.user_api_key import (
        PROVIDER_ANTHROPIC,
        get_user_anthropic_key,
        upsert_user_api_key,
    )

    raw = "sk-ant-roundtrip-secret-1234"
    await upsert_user_api_key(db, alice.id, PROVIDER_ANTHROPIC, raw, is_valid=True)
    decrypted = await get_user_anthropic_key(db, alice.id)
    assert decrypted == raw


async def test_full_key_never_appears_in_any_response(
    client, db, monkeypatch, alice
):
    """Defense in depth: even by mistake we must not echo the plaintext."""
    _patch_validator(monkeypatch, valid=True)
    _auth(client, alice)
    secret = "sk-ant-very-secret-do-not-leak-12345"
    put_r = await client.put(
        "/api/me/api-keys/anthropic", json={"api_key": secret}
    )
    list_r = await client.get("/api/me/api-keys")
    for r in (put_r, list_r):
        assert secret not in r.text, "plaintext key leaked in response body"


async def test_post_test_endpoint_valid_key(client, db, monkeypatch, alice):
    _patch_validator(monkeypatch, valid=True)
    _auth(client, alice)
    await client.put(
        "/api/me/api-keys/anthropic",
        json={"api_key": "sk-ant-test-endpoint-good-key-9988"},
    )

    async def fake_revalidate(db_, user_id, provider):
        return ValidationResult(True, None)

    monkeypatch.setattr(
        "app.api.routes.user_api_keys.revalidate_user_api_key", fake_revalidate
    )
    r = await client.post("/api/me/api-keys/anthropic/test")
    assert r.status_code == 200
    assert r.json()["valid"] is True


async def test_post_test_endpoint_invalid_key(client, db, monkeypatch, alice):
    _patch_validator(monkeypatch, valid=True)
    _auth(client, alice)
    await client.put(
        "/api/me/api-keys/anthropic",
        json={"api_key": "sk-ant-test-endpoint-good-key-9988"},
    )

    async def fake_revalidate(db_, user_id, provider):
        return ValidationResult(False, "key was revoked")

    monkeypatch.setattr(
        "app.api.routes.user_api_keys.revalidate_user_api_key", fake_revalidate
    )
    r = await client.post("/api/me/api-keys/anthropic/test")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert body["error"] == "key was revoked"


async def test_encrypted_in_db_not_plaintext(db, monkeypatch, alice):
    """The encrypted column must not equal the raw key. If Fernet ever
    breaks silently this catches it before secrets land at rest."""
    from sqlalchemy import select

    from app.models.user_api_key import UserApiKey
    from app.services.user_api_key import (
        PROVIDER_ANTHROPIC,
        upsert_user_api_key,
    )

    raw = "sk-ant-encryption-test-key-XYZA"
    await upsert_user_api_key(db, alice.id, PROVIDER_ANTHROPIC, raw, is_valid=True)
    row = (await db.execute(select(UserApiKey).where(UserApiKey.user_id == alice.id))).scalar_one()
    assert row.api_key_encrypted != raw
    assert raw not in row.api_key_encrypted
    assert row.key_last_four == "XYZA"


async def test_scan_without_key_fails_with_missing_api_key(db, monkeypatch, alice):
    """Scan engine must refuse to call Anthropic when the owner has no
    key configured, and surface MISSING_API_KEY on the scan row."""

    from app.models.repository import Repository
    from app.models.scan import Scan
    from app.services.scan_engine import run_scan

    repo = Repository(
        github_repo_id=99001,
        owner="alice",
        name="example",
        full_name="alice/example",
        default_branch="main",
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    scan = Scan(
        repository_id=repo.id,
        triggered_by_user_id=alice.id,
        status="pending",
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "e2e_test_mode", True)

    from app.integrations.anthropic_client import AnthropicError

    with pytest.raises(AnthropicError):
        await run_scan(db, scan.id)

    await db.refresh(scan)
    assert scan.status == "failed"
    assert scan.error is not None
    assert "MISSING_API_KEY" in scan.error
