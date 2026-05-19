import uuid
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings

_pool: ArqRedis | None = None


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        try:
            await _pool.aclose()
        except AttributeError:
            await _pool.close()
        _pool = None


async def enqueue_review(pull_request_id: uuid.UUID, **extra: Any) -> str:
    """Enqueue a review job. Dedup key uses pull_request_id so rapid resync
    events within the queue's keep-window collapse to one job."""
    pool = await get_pool()
    job_id = f"review:{pull_request_id}"
    job = await pool.enqueue_job(
        "review_pr",
        str(pull_request_id),
        extra,
        _job_id=job_id,
    )
    return job.job_id if job else job_id
