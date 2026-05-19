"""user repositories link + connected flag

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column(
            "connected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # backfill: any repo already linked via installation_repositories is connected
    op.execute(
        """
        UPDATE repositories r
        SET connected = TRUE
        WHERE EXISTS (
            SELECT 1 FROM installation_repositories ir
            WHERE ir.repository_id = r.id AND ir.deleted_at IS NULL
        )
        """
    )

    op.create_table(
        "user_repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_user_repositories_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"],
            name=op.f("fk_user_repositories_repository_id_repositories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_repositories")),
        sa.UniqueConstraint(
            "user_id", "repository_id",
            name="uq_user_repositories_pair",
        ),
    )
    op.create_index(
        "idx_user_repositories_user_id", "user_repositories", ["user_id"]
    )
    op.create_index(
        "idx_user_repositories_repository_id", "user_repositories", ["repository_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_user_repositories_repository_id", table_name="user_repositories")
    op.drop_index("idx_user_repositories_user_id", table_name="user_repositories")
    op.drop_table("user_repositories")
    op.drop_column("repositories", "connected")
