import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://reviewly:reviewly_dev_password@postgres:5432/reviewly",
)
os.environ.setdefault("REDIS_URL", "redis://redis:6379/0")
