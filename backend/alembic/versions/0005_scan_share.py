"""scan share tokens

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scans",
        sa.Column("share_token", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "scans",
        sa.Column("share_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ux_scans_share_token",
        "scans",
        ["share_token"],
        unique=True,
        postgresql_where=sa.text("share_token IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_scans_share_token", table_name="scans")
    op.drop_column("scans", "share_created_at")
    op.drop_column("scans", "share_token")
