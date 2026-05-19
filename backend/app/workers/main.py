from typing import Any

from arq.connections import RedisSettings

from app.config import get_settings
from app.core.logging import get_logger, setup_logging

setup_logging()
log = get_logger("reviewly.worker")
settings = get_settings()


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def ping(ctx) -> str:
    log.info("worker.ping")
    return "pong"


async def review_pr(ctx, pull_request_id: str, extra: dict[str, Any] | None = None) -> dict:
    """Placeholder for the actual review pipeline (phases 4-6).
    Logs the dispatch and returns a stub so the queue plumbing is end-to-end."""
    log.info("worker.review_pr.received", pr_id=pull_request_id, extra=extra or {})
    return {"pr_id": pull_request_id, "status": "queued_placeholder"}


async def on_startup(ctx) -> None:
    log.info("worker.startup", env=settings.app_env)


async def on_shutdown(ctx) -> None:
    log.info("worker.shutdown")


class WorkerSettings:
    redis_settings = _redis_settings()
    functions = [ping, review_pr]
    on_startup = on_startup
    on_shutdown = on_shutdown
    max_jobs = 10
    job_timeout = 300
    keep_result = 3600
