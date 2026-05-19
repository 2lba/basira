import asyncio
import json
import smtplib
import uuid
from email.message import EmailMessage

import redis.asyncio as aioredis

from app.config import get_settings
from app.core.crypto import CryptoError, decrypt_token
from app.core.logging import get_logger
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.user import User

log = get_logger("reviewly.notifier")

_E2E_LAST_EMAIL_KEY = "e2e:last_email"


def _scan_subject(scan: Scan, repo: Repository) -> str:
    if scan.status == "succeeded":
        return f"[reviewly] Scan of {repo.full_name} complete — score {scan.score}/100"
    if scan.status == "failed":
        return f"[reviewly] Scan of {repo.full_name} failed"
    return f"[reviewly] Scan of {repo.full_name} {scan.status}"


def _scan_body(scan: Scan, repo: Repository, frontend_url: str) -> str:
    lines: list[str] = []
    lines.append(f"Repository: {repo.full_name}")
    if scan.ref:
        lines.append(f"Branch: {scan.ref}")
    if scan.head_sha:
        lines.append(f"Commit: {scan.head_sha[:7]}")
    lines.append(f"Status: {scan.status}")
    if scan.score is not None:
        lines.append(f"Score: {scan.score}/100")
    if scan.summary:
        lines.append("")
        lines.append(scan.summary)
    if scan.counts:
        c = scan.counts
        lines.append("")
        lines.append(
            f"Findings: {c.get('total', 0)} "
            f"({c.get('critical', 0)} critical, {c.get('major', 0)} major, "
            f"{c.get('minor', 0)} minor, {c.get('nit', 0)} nit)"
        )
    if scan.error:
        lines.append("")
        lines.append(f"Error: {scan.error}")
    lines.append("")
    lines.append(f"View report: {frontend_url.rstrip('/')}/scans/{scan.id}")
    return "\n".join(lines)


def _send_smtp(
    *,
    host: str,
    port: int,
    use_tls: bool,
    username: str | None,
    password: str | None,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as s:
            if username and password:
                s.login(username, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=15) as s:
            if use_tls:
                s.starttls()
            if username and password:
                s.login(username, password)
            s.send_message(msg)


async def _store_e2e_email(payload: dict) -> None:
    r = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await r.set(_E2E_LAST_EMAIL_KEY, json.dumps(payload), ex=600)
    finally:
        await r.aclose()


async def get_last_e2e_email() -> dict | None:
    r = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        v = await r.get(_E2E_LAST_EMAIL_KEY)
        if v is None:
            return None
        return json.loads(v)
    finally:
        await r.aclose()


async def clear_last_e2e_email() -> None:
    r = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await r.delete(_E2E_LAST_EMAIL_KEY)
    finally:
        await r.aclose()


async def notify_scan_finished(
    scan: Scan, repo: Repository, user: User | None
) -> dict | None:
    """Send a scan-finished email if the user has SMTP configured and
    notifications enabled. Returns the payload that was sent (or None if
    notification was skipped). In e2e mode the payload is stashed in Redis
    instead of being sent over SMTP."""
    settings = get_settings()
    if user is None:
        return None
    if not user.notify_email_enabled:
        return None
    if not (user.smtp_host and user.smtp_port and user.smtp_from):
        return None
    recipient = user.email or user.smtp_from
    if not recipient:
        return None

    subject = _scan_subject(scan, repo)
    body = _scan_body(scan, repo, settings.frontend_base_url)

    payload = {
        "to": recipient,
        "from": user.smtp_from,
        "subject": subject,
        "body": body,
        "scan_id": str(scan.id),
    }

    if settings.e2e_test_mode:
        await _store_e2e_email(payload)
        log.info("notifier.e2e_stub", scan_id=str(scan.id))
        return payload

    password = None
    if user.smtp_password_encrypted:
        try:
            password = decrypt_token(user.smtp_password_encrypted)
        except CryptoError as e:
            log.warning("notifier.password_decrypt_failed", err=str(e))
            return None

    try:
        await asyncio.to_thread(
            _send_smtp,
            host=user.smtp_host,
            port=user.smtp_port,
            use_tls=user.smtp_use_tls,
            username=user.smtp_username,
            password=password,
            sender=user.smtp_from,
            recipient=recipient,
            subject=subject,
            body=body,
        )
        log.info("notifier.sent", scan_id=str(scan.id), to=recipient)
        return payload
    except Exception as e:
        log.warning(
            "notifier.send_failed",
            scan_id=str(scan.id),
            err=f"{e.__class__.__name__}: {str(e)[:200]}",
        )
        return None


async def notify_by_scan_id(db_factory, scan_id: uuid.UUID) -> None:
    """Worker-friendly entry point. Loads scan/repo/user fresh from DB."""
    async with db_factory() as db:
        scan = await db.get(Scan, scan_id)
        if scan is None:
            return
        repo = await db.get(Repository, scan.repository_id)
        if repo is None:
            return
        user = (
            await db.get(User, scan.triggered_by_user_id)
            if scan.triggered_by_user_id
            else None
        )
        await notify_scan_finished(scan, repo, user)
