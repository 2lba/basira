import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.crypto import (
    CryptoError,
    encrypt_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_expiry,
)
from app.integrations.github_oauth import GithubProfile
from app.models.refresh_token import RefreshToken
from app.models.user import User

LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 15 * 60


class AuthError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def _lockout_key(scope: str, ident: str) -> str:
    return f"auth:lockout:{scope}:{ident}"


async def is_locked_out(scope: str, ident: str) -> bool:
    r = await _get_redis()
    val = await r.get(_lockout_key(scope, ident))
    return val is not None and int(val) >= LOCKOUT_MAX_ATTEMPTS


async def record_failure(scope: str, ident: str) -> int:
    r = await _get_redis()
    key = _lockout_key(scope, ident)
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, LOCKOUT_WINDOW_SECONDS)
    count, _ = await pipe.execute()
    return int(count)


async def clear_failures(scope: str, ident: str) -> None:
    r = await _get_redis()
    await r.delete(_lockout_key(scope, ident))


async def upsert_user_from_github(
    db: AsyncSession, profile: GithubProfile, access_token: str
) -> User:
    try:
        enc = encrypt_token(access_token)
    except CryptoError as e:
        raise AuthError("CRYPTO_NOT_CONFIGURED", str(e)) from e

    stmt = select(User).where(User.github_user_id == profile.id)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None:
        user = User(
            github_user_id=profile.id,
            github_login=profile.login,
            email=profile.email,
            avatar_url=profile.avatar_url,
            access_token_encrypted=enc,
        )
        db.add(user)
    else:
        user.github_login = profile.login
        user.email = profile.email or user.email
        user.avatar_url = profile.avatar_url or user.avatar_url
        user.access_token_encrypted = enc

    await db.flush()
    await db.commit()
    await db.refresh(user)
    return user


async def issue_refresh(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_agent: str | None,
    ip: str | None,
    replaces: uuid.UUID | None = None,
) -> tuple[str, RefreshToken]:
    token = generate_refresh_token()
    rt = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(token),
        expires_at=refresh_expiry(),
        replaced_by=None,
        user_agent=(user_agent or "")[:512] or None,
        ip=(ip or "")[:64] or None,
    )
    db.add(rt)
    await db.flush()

    if replaces is not None:
        prev = await db.get(RefreshToken, replaces)
        if prev is not None:
            prev.revoked_at = datetime.now(UTC)
            prev.replaced_by = rt.id

    await db.commit()
    await db.refresh(rt)
    return token, rt


async def rotate_refresh(
    db: AsyncSession,
    presented_token: str,
    user_agent: str | None,
    ip: str | None,
) -> tuple[User, str]:
    h = hash_refresh_token(presented_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == h)
    rt = (await db.execute(stmt)).scalar_one_or_none()
    if rt is None:
        raise AuthError("REFRESH_INVALID", "refresh token invalid")

    now = datetime.now(UTC)
    if rt.revoked_at is not None:
        # token reuse detected; revoke entire family
        await _revoke_family(db, rt.user_id)
        raise AuthError("REFRESH_REUSED", "refresh token reused; session revoked")
    if rt.expires_at <= now:
        raise AuthError("REFRESH_EXPIRED", "refresh token expired")

    user = await db.get(User, rt.user_id)
    if user is None or user.deleted_at is not None:
        raise AuthError("USER_GONE", "user no longer exists")

    new_token, _ = await issue_refresh(db, user.id, user_agent, ip, replaces=rt.id)
    return user, new_token


async def revoke_refresh(db: AsyncSession, presented_token: str) -> None:
    h = hash_refresh_token(presented_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == h)
    rt = (await db.execute(stmt)).scalar_one_or_none()
    if rt is None or rt.revoked_at is not None:
        return
    rt.revoked_at = datetime.now(UTC)
    await db.commit()


async def _revoke_family(db: AsyncSession, user_id: uuid.UUID) -> None:
    stmt = select(RefreshToken).where(
        RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
    )
    rows = (await db.execute(stmt)).scalars().all()
    now = datetime.now(UTC)
    for r in rows:
        r.revoked_at = now
    await db.commit()
