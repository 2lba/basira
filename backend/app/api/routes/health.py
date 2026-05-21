from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app import __version__
from app.config import get_settings
from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness - process is up. Used by docker healthcheck."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(response: Response) -> dict:
    """Readiness - every dependency the API needs is reachable. Used by
    orchestrators before sending real traffic."""
    s = get_settings()
    out: dict = {"status": "ok", "db": "up", "redis": "up"}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        out["db"] = "down"
        out["db_error"] = exc.__class__.__name__
        out["status"] = "degraded"
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(s.redis_url, decode_responses=True)
        try:
            await r.ping()
        finally:
            await r.aclose()
    except Exception as exc:
        out["redis"] = "down"
        out["redis_error"] = exc.__class__.__name__
        out["status"] = "degraded"
    if out["status"] != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return out


@router.get("/version")
async def version() -> dict[str, str]:
    """Build info - git sha + version string. Helpful for matching a bug
    report to a deployment."""
    import os

    return {
        "name": "basira",
        "version": __version__,
        "git_sha": os.environ.get("GIT_SHA", "dev"),
        "env": get_settings().app_env,
    }
