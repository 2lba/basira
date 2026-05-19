import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "dVBTW1fvoM_FcogEF4ThvfRKNU6QlWqQ-Gtykc8Qrok=")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://reviewly:reviewly_dev_password@postgres:5432/reviewly",
)
os.environ.setdefault("REDIS_URL", "redis://redis:6379/0")

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
                    "review_comments, reviews, pull_requests, repositories, jobs "
                    "RESTART IDENTITY CASCADE"
                )
            )
        async for k in r.scan_iter(match="auth:lockout:*"):
            await r.delete(k)
        yield
    finally:
        await r.aclose()
        await engine.dispose()


@pytest.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
