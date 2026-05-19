"""slack + discord webhooks

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("slack_webhook_url_encrypted", sa.Text(), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column(
            "notify_slack_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("discord_webhook_url_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "notify_discord_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "notify_discord_enabled")
    op.drop_column("users", "discord_webhook_url_encrypted")
    op.drop_column("users", "notify_slack_enabled")
    op.drop_column("users", "slack_webhook_url_encrypted")
