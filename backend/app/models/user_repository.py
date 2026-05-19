import uuid

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class UserRepository(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    """OAuth-discovered link between a user and a repository. A repository
    appears in the user's list even if the app is not installed on it; the
    `Repository.connected` flag distinguishes the two."""

    __tablename__ = "user_repositories"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "repository_id",
            name="uq_user_repositories_pair",
        ),
        Index("idx_user_repositories_user_id", "user_id"),
        Index("idx_user_repositories_repository_id", "repository_id"),
    )
