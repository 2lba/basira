"""BYOK endpoints. Every route is JWT-protected.

PUT/POST routes are rate-limited 10/min per IP so a leaked password can't
be brute-forced against Anthropic by hammering /test.
"""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth_deps import current_user
from app.core.crypto import CryptoError
from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.user_api_key import (
    UserApiKeyCreate,
    UserApiKeyResponse,
    UserApiKeyTestResponse,
)
from app.services.user_api_key import (
    PROVIDER_ANTHROPIC,
    delete_user_api_key,
    get_user_api_key_row,
    revalidate_user_api_key,
    upsert_user_api_key,
    validate_anthropic_key,
)

router = APIRouter(prefix="/api/me/api-keys", tags=["api-keys"])

_RATE = "10/minute"


def _to_out(row) -> UserApiKeyResponse:
    return UserApiKeyResponse(
        provider=row.provider,
        key_last_four=row.key_last_four,
        is_valid=row.is_valid,
        last_validated_at=row.last_validated_at,
    )


@router.get("", response_model=list[UserApiKeyResponse])
async def list_api_keys(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the keys this user has configured. We never return the key
    itself - only `key_last_four`."""
    row = await get_user_api_key_row(db, user.id, PROVIDER_ANTHROPIC)
    return [_to_out(row)] if row else []


@router.put("/anthropic", response_model=UserApiKeyResponse)
@limiter.limit(_RATE)
async def put_anthropic_key(
    request: Request,
    body: UserApiKeyCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save or replace the user's Anthropic key. We validate first; an
    invalid key never lands in storage."""
    result = await validate_anthropic_key(body.api_key)
    if not result.valid:
        raise AppError(
            "INVALID_API_KEY",
            result.error or "anthropic rejected this key",
            status.HTTP_400_BAD_REQUEST,
        )
    try:
        row = await upsert_user_api_key(
            db, user.id, PROVIDER_ANTHROPIC, body.api_key, is_valid=True
        )
    except CryptoError as e:
        raise AppError(
            "CRYPTO_NOT_CONFIGURED",
            str(e),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from e
    return _to_out(row)


@router.delete("/anthropic", status_code=status.HTTP_204_NO_CONTENT)
async def delete_anthropic_key(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove the stored key. Returns 204 either way (idempotent)."""
    await delete_user_api_key(db, user.id, PROVIDER_ANTHROPIC)


@router.post("/anthropic/test", response_model=UserApiKeyTestResponse)
@limiter.limit(_RATE)
async def test_anthropic_key(
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-check the stored key against Anthropic and update is_valid.
    Costs ~one Haiku token; the rate limit keeps a leaked session from
    burning the host's budget."""
    result = await revalidate_user_api_key(db, user.id, PROVIDER_ANTHROPIC)
    return UserApiKeyTestResponse(valid=result.valid, error=result.error)
