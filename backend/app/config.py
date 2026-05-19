from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"  # noqa: S104
    app_port: int = 8000
    app_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5173"
    log_level: str = "INFO"

    secret_key: str = "change-me"  # noqa: S105
    token_encryption_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 60
    jwt_refresh_ttl_days: int = 7

    database_url: str = "postgresql+asyncpg://basira:basira_dev_password@postgres:5432/basira"
    redis_url: str = "redis://redis:6379/0"

    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-5"
    claude_max_tokens: int = 4096
    claude_temperature: float = 0.2

    github_app_id: str = ""
    github_app_client_id: str = ""
    github_app_client_secret: str = ""
    github_app_private_key_path: str = ""
    github_app_webhook_secret: str = ""
    github_app_name: str = "basira"

    cors_origins: str = "http://localhost:5173"

    review_max_files: int = 50
    review_max_diff_bytes: int = 200_000
    review_severity_threshold: str = "medium"

    rate_limit_general: str = "100/minute"
    rate_limit_auth: str = "5/minute"
    rate_limit_webhook: str = "120/minute"
    rate_limit_user_hourly: str = "1000/hour"

    e2e_test_mode: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
