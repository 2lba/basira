"""repo scan schedule

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column(
            "schedule_kind",
            sa.String(length=16),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column("repositories", sa.Column("schedule_dow", sa.Integer(), nullable=True))
    op.add_column("repositories", sa.Column("schedule_dom", sa.Integer(), nullable=True))
    op.add_column("repositories", sa.Column("schedule_hour", sa.Integer(), nullable=True))
    op.add_column(
        "repositories", sa.Column("schedule_minute", sa.Integer(), nullable=True)
    )
    op.add_column(
        "repositories",
        sa.Column("last_scheduled_run_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_repositories_schedule_kind",
        "repositories",
        ["schedule_kind"],
    )


def downgrade() -> None:
    op.drop_index("idx_repositories_schedule_kind", table_name="repositories")
    op.drop_column("repositories", "last_scheduled_run_at")
    op.drop_column("repositories", "schedule_minute")
    op.drop_column("repositories", "schedule_hour")
    op.drop_column("repositories", "schedule_dom")
    op.drop_column("repositories", "schedule_dow")
    op.drop_column("repositories", "schedule_kind")
