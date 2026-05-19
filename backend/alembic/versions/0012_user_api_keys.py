"""user-owned third-party api keys (BYOK)

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # current set: 'anthropic'. enum kept as varchar so adding providers
        # later is a one-line code change, not a migration.
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("key_last_four", sa.String(length=4), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_user_api_keys_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_api_keys")),
        sa.UniqueConstraint(
            "user_id", "provider",
            name="uq_user_api_keys_user_provider",
        ),
    )
    op.create_index("idx_user_api_keys_user_id", "user_api_keys", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_user_api_keys_user_id", table_name="user_api_keys")
    op.drop_table("user_api_keys")
