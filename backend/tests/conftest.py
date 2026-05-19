import os
import re

# Force tests onto a dedicated database. Past pytest runs nuked real users
# and scans because the autouse _clean_state fixture TRUNCATEs everything;
# pinning the DB name avoids that whatever DATABASE_URL the environment
# supplies. Set BASIRA_ALLOW_DB_WIPE=1 to opt back into the original URL
# (used in CI where the runner already owns an isolated db).
_default_db_url = "postgresql+asyncpg://basira:basira_dev_password@postgres:5432/basira"
if os.environ.get("BASIRA_ALLOW_DB_WIPE") != "1":
    src = os.environ.get("DATABASE_URL", _default_db_url)
    # rewrite the database name to end with _test so we can never touch the
    # real db by accident
    rewritten = re.sub(r"/([^/?]+)(\?|$)", r"/\1_test\2", src, count=1)
    if "_test" not in rewritten:
        rewritten = src.rsplit("/", 1)[0] + "/basira_test"
    os.environ["DATABASE_URL"] = rewritten

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "dVBTW1fvoM_FcogEF4ThvfRKNU6QlWqQ-Gtykc8Qrok=")
os.environ.setdefault("REDIS_URL", "redis://redis:6379/0")
os.environ.setdefault("GITHUB_APP_WEBHOOK_SECRET", "test_webhook_secret")

import pytest
import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.config import get_settings
from app.db.session import AsyncSessionLocal, engine
from app.main import app


@pytest.fixture(autouse=True)
async def _clean_state():
    settings = get_settings()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE TABLE refresh_tokens, users, "
                    "github_installations, installation_repositories, "
                    "user_repositories, scan_findings, scans, "
                    "review_comments, reviews, pull_requests, repositories, "
                    "jobs, webhook_events "
                    "RESTART IDENTITY CASCADE"
                )
            )
        await r.flushdb()
        yield
    finally:
        await r.aclose()
        await engine.dispose()
        from app.workers.queue import close_pool

        await close_pool()
        # reset cached singletons that hold sockets bound to this test's
        # event loop. Without this, the next test's calls into auth_service
        # or the worker queue crash with "Event loop is closed".
        import app.services.auth_service as _auth_svc

        _auth_svc._redis = None


@pytest.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
