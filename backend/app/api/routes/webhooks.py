import json

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.core.webhook_sig import WebhookSigError, verify_github_signature
from app.db.session import get_db
from app.services.webhooks import (
    SUPPORTED_EVENTS,
    WebhookProcessError,
    mark_processed,
    process_event,
    record_event,
)

log = get_logger("reviewly.webhook")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github")
@limiter.limit(get_settings().rate_limit_webhook)
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_github_delivery: str | None = Header(default=None, alias="X-GitHub-Delivery"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    body = await request.body()

    try:
        verify_github_signature(body, settings.github_app_webhook_secret, x_hub_signature_256)
    except WebhookSigError as e:
        log.warning("webhook.bad_signature", err=str(e), delivery=x_github_delivery)
        raise AppError(
            "INVALID_WEBHOOK_SIGNATURE",
            "webhook signature verification failed",
            status.HTTP_401_UNAUTHORIZED,
        ) from e

    if not x_github_event:
        raise AppError(
            "WEBHOOK_BAD_REQUEST",
            "missing X-GitHub-Event",
            status.HTTP_400_BAD_REQUEST,
        )
    if not x_github_delivery:
        raise AppError(
            "WEBHOOK_BAD_REQUEST",
            "missing X-GitHub-Delivery",
            status.HTTP_400_BAD_REQUEST,
        )

    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError as e:
        raise AppError(
            "WEBHOOK_BAD_REQUEST", "invalid json body", status.HTTP_400_BAD_REQUEST
        ) from e

    action = payload.get("action") if isinstance(payload, dict) else None

    if x_github_event not in SUPPORTED_EVENTS:
        log.info(
            "webhook.unsupported",
            gh_event=x_github_event,
            delivery=x_github_delivery,
        )
        return {"received": True, "ignored": True, "event": x_github_event}

    event_record, is_new = await record_event(
        db, x_github_delivery, x_github_event, action, payload
    )
    if not is_new:
        log.info("webhook.replay", delivery=x_github_delivery)
        return {"received": True, "duplicate": True}

    try:
        result = await process_event(db, event_record)
    except WebhookProcessError as e:
        await mark_processed(db, event_record, "failed", str(e))
        log.warning("webhook.process_failed", err=str(e), delivery=x_github_delivery)
        raise AppError("WEBHOOK_PROCESS_FAILED", str(e), status.HTTP_400_BAD_REQUEST) from e
    except Exception as e:
        await mark_processed(db, event_record, "errored", e.__class__.__name__)
        log.exception("webhook.unhandled", delivery=x_github_delivery)
        raise

    await mark_processed(db, event_record, "processed")
    log.info(
        "webhook.processed",
        gh_event=x_github_event,
        action=action,
        delivery=x_github_delivery,
    )
    return {"received": True, "result": result}
