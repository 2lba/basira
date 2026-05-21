"""BYOK service: encrypt user-supplied API keys at rest, validate them
against the upstream provider before persisting, and decrypt on demand
for the scan engine.

The plain key never leaves this module. Callers see a `UserApiKey` row
with `key_last_four` and never the encrypted payload.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import CryptoError, decrypt_token, encrypt_token
from app.core.logging import get_logger
from app.models.user_api_key import UserApiKey

log = get_logger("basira.byok")

PROVIDER_ANTHROPIC = "anthropic"


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    error: str | None = None


async def validate_anthropic_key(api_key: str) -> ValidationResult:
    """Ping Anthropic with the smallest possible request to confirm the key
    is live. Returns valid=True if the API accepts the key, valid=False
    plus a human-readable error otherwise.

    Cost: one `claude-haiku-4-5` call with `max_tokens=1` ≈ 0.0001 USD.
    """
    if not api_key or len(api_key) < 20:
        return ValidationResult(False, "key looks malformed")
    # e2e bypass: keys prefixed with sk-ant-e2e- skip the upstream call so
    # tests don't spend real budget or require a network round trip
    from app.config import get_settings

    if get_settings().e2e_test_mode and api_key.startswith("sk-ant-e2e-"):
        return ValidationResult(True, None)
    try:
        from anthropic import AsyncAnthropic
    except ImportError:  # pragma: no cover
        return ValidationResult(False, "anthropic sdk not installed")

    try:
        from anthropic import APIStatusError, AuthenticationError
    except ImportError:
        APIStatusError = Exception  # type: ignore[misc,assignment]
        AuthenticationError = Exception  # type: ignore[misc,assignment]

    client = AsyncAnthropic(api_key=api_key)
    try:
        await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1,
            messages=[{"role": "user", "content": "ok"}],
        )
        return ValidationResult(True, None)
    except AuthenticationError:
        return ValidationResult(False, "key was rejected by anthropic")
    except APIStatusError as e:
        status = getattr(e, "status_code", "?")
        return ValidationResult(False, f"anthropic returned {status}")
    except Exception as e:
        # network / transient — bubble up the class name only, don't leak
        # internals into the user-facing message
        return ValidationResult(False, f"validation failed: {e.__class__.__name__}")


async def upsert_user_api_key(
    db: AsyncSession,
    user_id: uuid.UUID,
    provider: str,
    raw_key: str,
    is_valid: bool,
) -> UserApiKey:
    raw_key = raw_key.strip()
    last_four = raw_key[-4:] if len(raw_key) >= 4 else raw_key
    try:
        encrypted = encrypt_token(raw_key)
    except CryptoError as e:
        # surface so the route can return a 503 instead of a vague 500
        raise

    stmt = select(UserApiKey).where(
        UserApiKey.user_id == user_id,
        UserApiKey.provider == provider,
        UserApiKey.deleted_at.is_(None),
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    now = datetime.now(UTC)
    if existing is None:
        row = UserApiKey(
            user_id=user_id,
            provider=provider,
            api_key_encrypted=encrypted,
            key_last_four=last_four,
            is_valid=is_valid,
            last_validated_at=now if is_valid else None,
        )
        db.add(row)
    else:
        existing.api_key_encrypted = encrypted
        existing.key_last_four = last_four
        existing.is_valid = is_valid
        existing.last_validated_at = now if is_valid else existing.last_validated_at
        row = existing
    await db.commit()
    await db.refresh(row)
    log.info(
        "byok.key_saved",
        user_id=str(user_id),
        provider=provider,
        valid=is_valid,
    )
    return row


async def delete_user_api_key(
    db: AsyncSession, user_id: uuid.UUID, provider: str
) -> bool:
    stmt = select(UserApiKey).where(
        UserApiKey.user_id == user_id,
        UserApiKey.provider == provider,
        UserApiKey.deleted_at.is_(None),
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return False
    row.deleted_at = datetime.now(UTC)
    await db.commit()
    log.info("byok.key_removed", user_id=str(user_id), provider=provider)
    return True


async def get_user_api_key_row(
    db: AsyncSession, user_id: uuid.UUID, provider: str
) -> UserApiKey | None:
    stmt = select(UserApiKey).where(
        UserApiKey.user_id == user_id,
        UserApiKey.provider == provider,
        UserApiKey.deleted_at.is_(None),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_anthropic_key(
    db: AsyncSession, user_id: uuid.UUID
) -> str | None:
    """Decrypt and return the user's Anthropic API key, or None if they
    don't have one configured. Callers should treat None as a signal to
    fail the scan with MISSING_API_KEY."""
    row = await get_user_api_key_row(db, user_id, PROVIDER_ANTHROPIC)
    if row is None:
        return None
    try:
        return decrypt_token(row.api_key_encrypted)
    except CryptoError as e:
        log.warning("byok.decrypt_failed", user_id=str(user_id), err=str(e))
        return None


async def revalidate_user_api_key(
    db: AsyncSession, user_id: uuid.UUID, provider: str
) -> ValidationResult:
    """Re-check the key against the provider and update is_valid. Used by
    the test endpoint to give the user a fresh read."""
    row = await get_user_api_key_row(db, user_id, provider)
    if row is None:
        return ValidationResult(False, "no key configured")
    try:
        plain = decrypt_token(row.api_key_encrypted)
    except CryptoError:
        return ValidationResult(False, "stored key is unreadable")
    if provider == PROVIDER_ANTHROPIC:
        result = await validate_anthropic_key(plain)
    else:
        result = ValidationResult(False, f"unknown provider: {provider}")
    row.is_valid = result.valid
    if result.valid:
        row.last_validated_at = datetime.now(UTC)
    await db.commit()
    log.info(
        "byok.key_validated",
        user_id=str(user_id),
        provider=provider,
        valid=result.valid,
    )
    return result
