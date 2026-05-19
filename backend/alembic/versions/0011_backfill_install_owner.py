"""backfill installation user_id from account_login

Wave-4.5 ownership fix: existing rows in github_installations have user_id =
NULL because the webhook handler never set it. For User-type installations
this matches account_login -> users.github_login (with github_user_id as a
preferred match). Org installs are left NULL — they have no single owner.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # prefer github_user_id (stable across renames), then login
    op.execute(
        """
        UPDATE github_installations gi
        SET user_id = u.id
        FROM users u
        WHERE gi.user_id IS NULL
          AND gi.account_type ILIKE 'user'
          AND u.github_user_id = gi.account_id
        """
    )
    op.execute(
        """
        UPDATE github_installations gi
        SET user_id = u.id
        FROM users u
        WHERE gi.user_id IS NULL
          AND gi.account_type ILIKE 'user'
          AND u.github_login = gi.account_login
        """
    )


def downgrade() -> None:
    # not a structural change; nothing reversible. leave the assignments.
    pass
