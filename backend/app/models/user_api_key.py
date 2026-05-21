import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class UserApiKey(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    """User-owned third-party API key (BYOK).

    Stores the key encrypted at rest with the app's Fernet key. The plain
    value is never returned via the API - only `key_last_four` is shown
    so the user can recognise it.
    """

    __tablename__ = "user_api_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    key_last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "provider",
            name="uq_user_api_keys_user_provider",
        ),
        Index("idx_user_api_keys_user_id", "user_id"),
    )
