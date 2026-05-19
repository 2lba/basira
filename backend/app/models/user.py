from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class User(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    github_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    github_login: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    smtp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    smtp_from: Mapped[str | None] = mapped_column(String(320), nullable=True)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_email_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    __table_args__ = (Index("idx_users_github_login", "github_login"),)
