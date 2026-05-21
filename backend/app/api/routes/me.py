import ipaddress
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import current_user
from app.core.crypto import CryptoError, encrypt_token
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ChatWebhookOut,
    ChatWebhookUpdate,
    SmtpSettingsOut,
    SmtpSettingsUpdate,
)

router = APIRouter(prefix="/api/me", tags=["me"])


# Cloud metadata endpoints + common loopback hostnames that an SSRF would
# target. We block them on top of the IP-range checks below.
_BLOCKED_HOSTS = {
    "metadata.google.internal",
    "metadata.goog",
    "169.254.169.254",
    "fd00:ec2::254",
    "localhost",
    "ip6-localhost",
    "ip6-loopback",
}


def _validate_webhook_url(url: str, kind: str) -> str:
    """Reject anything that isn't a public http(s) URL. Closes SSRF - without
    this a user can point Slack/Discord at AWS IMDS, internal services, or
    file:// and exfiltrate / probe."""
    url = url.strip()
    if len(url) > 2048:
        raise AppError(
            "BAD_URL",
            "webhook url too long",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise AppError(
            "BAD_URL",
            "webhook url must use http(s)://",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    host = (parsed.hostname or "").lower()
    if not host:
        raise AppError(
            "BAD_URL",
            "webhook url is missing a host",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if host in _BLOCKED_HOSTS:
        raise AppError(
            "BAD_URL",
            "webhook url points at an internal host",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    # if the host parses as an IP literal, reject private/reserved ranges.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise AppError(
            "BAD_URL",
            "webhook url points at an internal address",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return url


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


def _chat_to_out(url_field: str | None, enabled: bool) -> ChatWebhookOut:
    return ChatWebhookOut(url_set=bool(url_field), enabled=enabled)


@router.get("/slack", response_model=ChatWebhookOut)
async def get_slack(user: User = Depends(current_user)):
    return _chat_to_out(user.slack_webhook_url_encrypted, user.notify_slack_enabled)


@router.patch("/slack", response_model=ChatWebhookOut)
async def update_slack(
    body: ChatWebhookUpdate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.clear:
        user.slack_webhook_url_encrypted = None
        user.notify_slack_enabled = False
    elif body.url is not None and body.url != "":
        url = _validate_webhook_url(body.url, "slack")
        try:
            user.slack_webhook_url_encrypted = encrypt_token(url)
        except CryptoError as e:
            raise AppError(
                "CRYPTO_NOT_CONFIGURED", str(e), status.HTTP_503_SERVICE_UNAVAILABLE
            ) from e
    if body.enabled is not None:
        if body.enabled and not user.slack_webhook_url_encrypted:
            raise AppError(
                "WEBHOOK_MISSING",
                "set the slack webhook url before enabling",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        user.notify_slack_enabled = bool(body.enabled)

    await db.commit()
    await db.refresh(user)
    return _chat_to_out(user.slack_webhook_url_encrypted, user.notify_slack_enabled)


@router.get("/discord", response_model=ChatWebhookOut)
async def get_discord(user: User = Depends(current_user)):
    return _chat_to_out(
        user.discord_webhook_url_encrypted, user.notify_discord_enabled
    )


@router.patch("/discord", response_model=ChatWebhookOut)
async def update_discord(
    body: ChatWebhookUpdate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.clear:
        user.discord_webhook_url_encrypted = None
        user.notify_discord_enabled = False
    elif body.url is not None and body.url != "":
        url = _validate_webhook_url(body.url, "discord")
        try:
            user.discord_webhook_url_encrypted = encrypt_token(url)
        except CryptoError as e:
            raise AppError(
                "CRYPTO_NOT_CONFIGURED", str(e), status.HTTP_503_SERVICE_UNAVAILABLE
            ) from e
    if body.enabled is not None:
        if body.enabled and not user.discord_webhook_url_encrypted:
            raise AppError(
                "WEBHOOK_MISSING",
                "set the discord webhook url before enabling",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        user.notify_discord_enabled = bool(body.enabled)

    await db.commit()
    await db.refresh(user)
    return _chat_to_out(
        user.discord_webhook_url_encrypted, user.notify_discord_enabled
    )
