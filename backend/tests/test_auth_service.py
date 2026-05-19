import pytest

from app.integrations.github_oauth import GithubProfile
from app.services.auth_service import (
    LOCKOUT_MAX_ATTEMPTS,
    AuthError,
    clear_failures,
    is_locked_out,
    issue_refresh,
    record_failure,
    rotate_refresh,
    upsert_user_from_github,
)


async def test_should_lock_out_when_threshold_reached():
    ip = "10.0.0.1"
    for _ in range(LOCKOUT_MAX_ATTEMPTS - 1):
        await record_failure("oauth", ip)
    assert not await is_locked_out("oauth", ip)
    await record_failure("oauth", ip)
    assert await is_locked_out("oauth", ip)
    await clear_failures("oauth", ip)
    assert not await is_locked_out("oauth", ip)


async def test_should_create_user_when_first_oauth(db):
    profile = GithubProfile(id=123, login="alice", email="a@example.com", avatar_url=None)
    user = await upsert_user_from_github(db, profile, access_token="ghp_test_123")
    assert user.github_user_id == 123
    assert user.github_login == "alice"
    assert user.access_token_encrypted
    assert user.access_token_encrypted != "ghp_test_123"


async def test_should_update_user_when_repeat_oauth(db):
    p1 = GithubProfile(id=42, login="bob", email=None, avatar_url=None)
    u1 = await upsert_user_from_github(db, p1, access_token="t1")
    p2 = GithubProfile(id=42, login="bob_renamed", email="b@example.com", avatar_url=None)
    u2 = await upsert_user_from_github(db, p2, access_token="t2")
    assert u1.id == u2.id
    assert u2.github_login == "bob_renamed"
    assert u2.email == "b@example.com"


async def test_should_rotate_refresh_when_valid(db):
    profile = GithubProfile(id=7, login="r", email=None, avatar_url=None)
    user = await upsert_user_from_github(db, profile, access_token="t")
    tok, _ = await issue_refresh(db, user.id, None, None)
    user2, new_tok = await rotate_refresh(db, tok, None, None)
    assert user2.id == user.id
    assert new_tok != tok


async def test_should_revoke_family_when_token_reused(db):
    profile = GithubProfile(id=8, login="r2", email=None, avatar_url=None)
    user = await upsert_user_from_github(db, profile, access_token="t")
    tok, _ = await issue_refresh(db, user.id, None, None)
    await rotate_refresh(db, tok, None, None)
    with pytest.raises(AuthError) as exc:
        await rotate_refresh(db, tok, None, None)
    assert exc.value.code == "REFRESH_REUSED"
