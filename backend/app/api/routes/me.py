from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import current_user
from app.core.crypto import CryptoError, encrypt_token
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import SmtpSettingsOut, SmtpSettingsUpdate

router = APIRouter(prefix="/api/me", tags=["me"])


def _to_out(u: User) -> SmtpSettingsOut:
    return SmtpSettingsOut(
        smtp_host=u.smtp_host,
        smtp_port=u.smtp_port,
        smtp_username=u.smtp_username,
        smtp_from=u.smtp_from,
        smtp_use_tls=u.smtp_use_tls,
        notify_email_enabled=u.notify_email_enabled,
        password_set=bool(u.smtp_password_encrypted),
    )


@router.get("/smtp", response_model=SmtpSettingsOut)
async def get_smtp(user: User = Depends(current_user)):
    return _to_out(user)


@router.patch("/smtp", response_model=SmtpSettingsOut)
async def update_smtp(
    body: SmtpSettingsUpdate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.smtp_host is not None:
        user.smtp_host = body.smtp_host.strip() or None
    if body.smtp_port is not None:
        user.smtp_port = body.smtp_port
    if body.smtp_username is not None:
        user.smtp_username = body.smtp_username.strip() or None
    if body.smtp_from is not None:
        user.smtp_from = str(body.smtp_from)
    if body.smtp_use_tls is not None:
        user.smtp_use_tls = bool(body.smtp_use_tls)
    if body.clear_password:
        user.smtp_password_encrypted = None
    elif body.smtp_password is not None and body.smtp_password != "":
        try:
            user.smtp_password_encrypted = encrypt_token(body.smtp_password)
        except CryptoError as e:
            raise AppError(
                "CRYPTO_NOT_CONFIGURED",
                str(e),
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from e
    if body.notify_email_enabled is not None:
        if body.notify_email_enabled and not (
            user.smtp_host and user.smtp_port and user.smtp_from
        ):
            raise AppError(
                "SMTP_INCOMPLETE",
                "configure smtp host, port and from before enabling notifications",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        user.notify_email_enabled = bool(body.notify_email_enabled)

    await db.commit()
    await db.refresh(user)
    return _to_out(user)
