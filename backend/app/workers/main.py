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


async def on_startup(ctx) -> None:
    log.info("worker.startup", env=settings.app_env)


async def on_shutdown(ctx) -> None:
    log.info("worker.shutdown")


class WorkerSettings:
    redis_settings = _redis_settings()
    functions = [ping]
    on_startup = on_startup
    on_shutdown = on_shutdown
    max_jobs = 10
    job_timeout = 300
    keep_result = 3600
