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
    import uuid

    from app.db.session import AsyncSessionLocal
    from app.models.pull_request import PullRequest
    from app.services.review_engine import run_review

    log.info("worker.review_pr.start", pr_id=pull_request_id, extra=extra or {})
    pr_uuid = uuid.UUID(pull_request_id)

    async with AsyncSessionLocal() as db:
        pr = await db.get(PullRequest, pr_uuid)
        if pr is None:
            log.warning("worker.review_pr.missing", pr_id=pull_request_id)
            return {"pr_id": pull_request_id, "status": "missing"}

        try:
            outcome = await run_review(db, pr)
        except Exception as e:
            log.exception("worker.review_pr.failed", pr_id=pull_request_id)
            return {"pr_id": pull_request_id, "status": "failed", "err": str(e)[:200]}

    return {
        "pr_id": pull_request_id,
        "status": outcome.review.status,
        "review_id": str(outcome.review.id),
        "comments": outcome.comments_created,
        "cached": outcome.skipped_existing,
    }


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
