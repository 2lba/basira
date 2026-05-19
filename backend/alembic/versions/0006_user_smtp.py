"""user smtp settings

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("smtp_host", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("smtp_port", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("smtp_username", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("smtp_password_encrypted", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("smtp_from", sa.String(length=320), nullable=True))
    op.add_column(
        "users",
        sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "users",
        sa.Column(
            "notify_email_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "notify_email_enabled")
    op.drop_column("users", "smtp_use_tls")
    op.drop_column("users", "smtp_from")
    op.drop_column("users", "smtp_password_encrypted")
    op.drop_column("users", "smtp_username")
    op.drop_column("users", "smtp_port")
    op.drop_column("users", "smtp_host")
