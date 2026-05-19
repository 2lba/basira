"""End-to-end test fixtures. Mounted only when e2e_test_mode is enabled.

These endpoints let a Playwright test seed a user/repo/installation directly
without going through real OAuth or GitHub App flows. They are not registered
in production builds.
"""
import json
import secrets

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth_deps import ACCESS_COOKIE, REFRESH_COOKIE
from app.core.crypto import issue_access_token
from app.db.session import get_db
from app.models.installation import GithubInstallation, InstallationRepository
from app.models.repository import Repository
from app.models.scan import Scan, ScanFinding
from app.models.user import User
from app.services.auth_service import issue_refresh

router = APIRouter(prefix="/test", tags=["test"])


class SeedRequest(BaseModel):
    github_login: str = "playwright-user"
    repo_full_name: str = "playwright-user/sample-repo"
    private: bool = False
    default_branch: str = "main"


class SeedResponse(BaseModel):
    user_id: str
    repo_id: str
    repo_full_name: str
    installation_id: int


@router.post("/reset", status_code=status.HTTP_200_OK)
async def reset(db: AsyncSession = Depends(get_db)):
    """Hard-delete e2e fixtures. Only runs in test mode."""
    from sqlalchemy import delete

    await db.execute(delete(ScanFinding))
    await db.execute(delete(Scan))
    await db.execute(delete(InstallationRepository))
    await db.execute(delete(GithubInstallation))
    await db.execute(delete(Repository))
    await db.execute(delete(User).where(User.github_login.like("playwright%")))
    await db.commit()
    return {"ok": True}


@router.post("/seed", response_model=SeedResponse)
async def seed(
    body: SeedRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    s = get_settings()
    owner, name = body.repo_full_name.split("/", 1)

    # user
    user = User(
        github_user_id=secrets.randbelow(10_000_000) + 1_000_000,
        github_login=body.github_login,
        email=f"{body.github_login}@example.test",
        avatar_url=None,
        access_token_encrypted=None,
    )
    db.add(user)
    await db.flush()

    # repository
    repo = Repository(
        github_repo_id=secrets.randbelow(10_000_000) + 1_000_000,
        owner=owner,
        name=name,
        full_name=body.repo_full_name,
        default_branch=body.default_branch,
        private=body.private,
        review_enabled=True,
        severity_threshold="minor",
    )
    db.add(repo)
    await db.flush()

    # installation
    installation_id_int = secrets.randbelow(10_000_000) + 1_000_000
    inst = GithubInstallation(
        installation_id=installation_id_int,
        account_login=owner,
        account_type="User",
        account_id=user.github_user_id,
        user_id=user.id,
    )
    db.add(inst)
    await db.flush()

    db.add(
        InstallationRepository(
            installation_id=inst.id,
            repository_id=repo.id,
        )
    )
    await db.commit()
    await db.refresh(user)
    await db.refresh(repo)
    await db.refresh(inst)

    # auth cookies
    access = issue_access_token(str(user.id), {"login": user.github_login})
    refresh_token, _ = await issue_refresh(
        db,
        user.id,
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
    )
    cookie_opts = {
        "httponly": True,
        "secure": s.is_production,
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=s.jwt_access_ttl_minutes * 60,
        **cookie_opts,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=s.jwt_refresh_ttl_days * 86400,
        **cookie_opts,
    )

    return SeedResponse(
        user_id=str(user.id),
        repo_id=str(repo.id),
        repo_full_name=repo.full_name,
        installation_id=installation_id_int,
    )


class FinalizeScanRequest(BaseModel):
    scan_id: str


@router.post("/scans/{scan_id}/finalize-now")
async def finalize_now(scan_id: str, db: AsyncSession = Depends(get_db)):
    """Force the most-recent pending/running scan for the e2e fixture into a
    successful terminal state with deterministic findings. Avoids depending on
    the worker / external services."""
    import uuid as _uuid

    sid = _uuid.UUID(scan_id)
    scan = await db.get(Scan, sid)
    if scan is None:
        return {"ok": False, "reason": "not found"}

    scan.status = "succeeded"
    scan.progress = 100
    scan.progress_message = "done"
    scan.head_sha = scan.head_sha or "deadbeefcafef00d1234567890abcdef12345678"
    scan.ref = scan.ref or "main"
    scan.files_scanned = 8
    scan.files_skipped = 2
    scan.model = "claude-sonnet-4-5"
    scan.tokens_input = 4200
    scan.tokens_output = 380
    scan.cost_usd = 0.018

    findings = [
        {
            "path": "app/auth.py",
            "line": 42,
            "severity": "critical",
            "category": "security",
            "message": "Token compared with ==, vulnerable to timing attack.",
            "suggestion": "use secrets.compare_digest(a, b)",
            "confidence": 0.95,
        },
        {
            "path": "app/db.py",
            "line": 117,
            "severity": "major",
            "category": "performance",
            "message": "N+1 query in user listing; preload memberships with joinedload.",
            "suggestion": None,
            "confidence": 0.82,
        },
        {
            "path": "app/views.py",
            "line": 8,
            "severity": "minor",
            "category": "maintainability",
            "message": "Function is 60 lines; consider extracting permission check.",
            "suggestion": None,
            "confidence": 0.6,
        },
        {
            "path": "scripts/build.sh",
            "line": None,
            "severity": "nit",
            "category": "style",
            "message": "Missing trailing newline at end of file.",
            "suggestion": None,
            "confidence": 0.4,
        },
    ]
    counts = {"total": 4, "critical": 1, "major": 1, "minor": 1, "nit": 1}
    scan.counts = counts
    scan.score = 100 - (1 * 20 + 1 * 8 + 1 * 3 + 1 * 1)  # 68
    scan.summary = "Scanned 8 files. Found 1 critical, 1 major, 1 minor, 1 nit issues."

    from datetime import UTC, datetime

    scan.started_at = scan.started_at or datetime.now(UTC)
    scan.finished_at = datetime.now(UTC)

    # remove any pre-existing findings for idempotency
    existing = (
        await db.execute(select(ScanFinding).where(ScanFinding.scan_id == scan.id))
    ).scalars().all()
    for ef in existing:
        await db.delete(ef)

    for f in findings:
        db.add(
            ScanFinding(
                scan_id=scan.id,
                path=f["path"],
                line=f["line"],
                severity=f["severity"],
                category=f["category"],
                message=f["message"],
                suggestion=f["suggestion"],
                confidence=f["confidence"],
            )
        )

    await db.commit()
    return {"ok": True, "scan_id": str(scan.id), "score": scan.score}


@router.get("/last-email")
async def get_last_email():
    from app.services.notifier import get_last_e2e_email

    payload = await get_last_e2e_email()
    return {"email": payload}


@router.post("/last-email/clear")
async def clear_last_email():
    from app.services.notifier import clear_last_e2e_email

    await clear_last_e2e_email()
    return {"ok": True}


_SINK_PREFIX = "e2e:webhook_sink:"


async def _redis():
    import redis.asyncio as aioredis

    return aioredis.from_url(get_settings().redis_url, decode_responses=True)


@router.post("/webhook-sink/{kind}")
async def sink_post(kind: str, request: Request):
    if kind not in ("slack", "discord", "generic"):
        return {"ok": False, "reason": "unknown kind"}
    body_bytes = await request.body()
    try:
        payload = json.loads(body_bytes.decode() or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {"raw": body_bytes.decode(errors="replace")}
    r = await _redis()
    try:
        await r.set(_SINK_PREFIX + kind, json.dumps(payload), ex=600)
    finally:
        await r.aclose()
    return {"ok": True}


@router.get("/webhook-sink/{kind}")
async def sink_get(kind: str):
    r = await _redis()
    try:
        v = await r.get(_SINK_PREFIX + kind)
    finally:
        await r.aclose()
    return {"payload": json.loads(v) if v else None}


@router.post("/webhook-sink/{kind}/clear")
async def sink_clear(kind: str):
    r = await _redis()
    try:
        await r.delete(_SINK_PREFIX + kind)
    finally:
        await r.aclose()
    return {"ok": True}
