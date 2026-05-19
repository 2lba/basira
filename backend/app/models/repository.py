from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class Repository(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "repositories"

    github_repo_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    review_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    severity_threshold: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    ignored_paths: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    custom_rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_override: Mapped[str | None] = mapped_column(String(64), nullable=True)

    schedule_kind: Mapped[str] = mapped_column(String(16), default="none", nullable=False)
    schedule_dow: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_dom: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_scheduled_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ignored_categories: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    false_positive_keys: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_repositories_full_name", "full_name"),
        Index("idx_repositories_owner", "owner"),
        Index("idx_repositories_schedule_kind", "schedule_kind"),
    )
