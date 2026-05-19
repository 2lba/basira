"""finding actions

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scan_findings",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "scan_findings",
        sa.Column("false_positive_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "scan_findings",
        sa.Column("dedup_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "idx_scan_findings_dedup_key", "scan_findings", ["dedup_key"]
    )

    op.add_column(
        "repositories",
        sa.Column(
            "ignored_categories",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "repositories",
        sa.Column(
            "false_positive_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("repositories", "false_positive_keys")
    op.drop_column("repositories", "ignored_categories")
    op.drop_index("idx_scan_findings_dedup_key", table_name="scan_findings")
    op.drop_column("scan_findings", "dedup_key")
    op.drop_column("scan_findings", "false_positive_at")
    op.drop_column("scan_findings", "resolved_at")
