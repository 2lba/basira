from typing import Any

from arq.connections import RedisSettings
from arq.cron import cron

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
    from app.services.comment_poster import post_review_to_github
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

        if outcome.skipped_existing:
            return {
                "pr_id": pull_request_id,
                "status": "cached",
                "review_id": str(outcome.review.id),
            }

        try:
            posted = await post_review_to_github(db, outcome.review)
        except Exception as e:
            log.exception("worker.review_pr.post_failed", pr_id=pull_request_id)
            return {
                "pr_id": pull_request_id,
                "status": "review_succeeded_post_failed",
                "review_id": str(outcome.review.id),
                "comments": outcome.comments_created,
                "err": str(e)[:200],
            }

    return {
        "pr_id": pull_request_id,
        "status": outcome.review.status,
        "review_id": str(outcome.review.id),
        "comments": outcome.comments_created,
        "github_review_id": posted.get("github_review_id"),
    }


async def on_startup(ctx) -> None:
    log.info("worker.startup", env=settings.app_env)


async def on_shutdown(ctx) -> None:
    log.info("worker.shutdown")


async def scan_repo(ctx, scan_id: str) -> dict:
    import uuid

    from app.db.session import AsyncSessionLocal
    from app.services.notifier import notify_by_scan_id
    from app.services.scan_engine import run_scan

    log.info("worker.scan_repo.start", scan_id=scan_id)
    sid = uuid.UUID(scan_id)
    async with AsyncSessionLocal() as db:
        try:
            outcome = await run_scan(db, sid)
            result = {
                "scan_id": scan_id,
                "status": outcome.scan.status,
                "findings": outcome.findings_created,
                "score": outcome.scan.score,
            }
        except Exception as e:
            log.exception("worker.scan_repo.failed", scan_id=scan_id)
            result = {"scan_id": scan_id, "status": "failed", "err": str(e)[:200]}

    try:
        await notify_by_scan_id(AsyncSessionLocal, sid)
    except Exception:
        log.exception("worker.scan_repo.notify_failed", scan_id=scan_id)
    return result


async def scheduler_tick(ctx) -> int:
    from app.db.session import AsyncSessionLocal
    from app.services.scheduler import run_due_scheduled_scans

    async with AsyncSessionLocal() as db:
        created = await run_due_scheduled_scans(db)
    if created:
        log.info("worker.scheduler_tick.enqueued", count=len(created))
    return len(created)


class WorkerSettings:
    redis_settings = _redis_settings()
    functions = [ping, review_pr, scan_repo]
    cron_jobs = [cron(scheduler_tick, minute=set(range(60)))]
    on_startup = on_startup
    on_shutdown = on_shutdown
    max_jobs = 10
    job_timeout = 1800
    keep_result = 3600
