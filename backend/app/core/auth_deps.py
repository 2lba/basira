import uuid

from fastapi import Cookie, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import CryptoError, verify_access_token
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User

ACCESS_COOKIE = "basira_access"
REFRESH_COOKIE = "basira_refresh"
CSRF_STATE_COOKIE = "basira_oauth_state"
POST_LOGIN_REDIRECT_COOKIE = "basira_post_login"


async def current_user(
    access: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not access:
        raise AppError("NOT_AUTHENTICATED", "not authenticated", status.HTTP_401_UNAUTHORIZED)
    try:
        payload = verify_access_token(access)
    except CryptoError as e:
        raise AppError("INVALID_TOKEN", "invalid token", status.HTTP_401_UNAUTHORIZED) from e
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as e:
        raise AppError(
            "INVALID_TOKEN", "invalid token subject", status.HTTP_401_UNAUTHORIZED
        ) from e
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise AppError("USER_GONE", "user not found", status.HTTP_401_UNAUTHORIZED)
    return user
