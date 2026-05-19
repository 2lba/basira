"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_user_id", sa.BigInteger(), nullable=False),
        sa.Column("github_login", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("access_token_encrypted", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("github_user_id", name=op.f("uq_users_github_user_id")),
    )
    op.create_index("idx_users_github_login", "users", ["github_login"])

    op.create_table(
        "github_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("account_login", sa.String(length=255), nullable=False),
        sa.Column("account_type", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_github_installations_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_github_installations")),
        sa.UniqueConstraint(
            "installation_id", name=op.f("uq_github_installations_installation_id")
        ),
    )
    op.create_index(
        "idx_github_installations_user_id", "github_installations", ["user_id"]
    )

    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_repo_id", sa.BigInteger(), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=512), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=True),
        sa.Column("private", sa.Boolean(), nullable=False),
        sa.Column("review_enabled", sa.Boolean(), nullable=False),
        sa.Column("severity_threshold", sa.String(length=32), nullable=False),
        sa.Column("ignored_paths", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("custom_rules", sa.Text(), nullable=True),
        sa.Column("model_override", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repositories")),
        sa.UniqueConstraint("github_repo_id", name=op.f("uq_repositories_github_repo_id")),
    )
    op.create_index("idx_repositories_full_name", "repositories", ["full_name"])
    op.create_index("idx_repositories_owner", "repositories", ["owner"])

    op.create_table(
        "installation_repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["installation_id"],
            ["github_installations.id"],
            name=op.f("fk_installation_repositories_installation_id_github_installations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_installation_repositories_repository_id_repositories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_installation_repositories")),
        sa.UniqueConstraint(
            "installation_id",
            "repository_id",
            name="uq_installation_repositories_pair",
        ),
    )
    op.create_index(
        "idx_installation_repositories_installation_id",
        "installation_repositories",
        ["installation_id"],
    )
    op.create_index(
        "idx_installation_repositories_repository_id",
        "installation_repositories",
        ["repository_id"],
    )

    op.create_table(
        "pull_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_pr_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("head_sha", sa.String(length=64), nullable=False),
        sa.Column("base_sha", sa.String(length=64), nullable=True),
        sa.Column("author_login", sa.String(length=255), nullable=True),
        sa.Column("draft", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_pull_requests_repository_id_repositories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pull_requests")),
        sa.UniqueConstraint(
            "repository_id", "number", name="uq_pull_requests_repo_number"
        ),
    )
    op.create_index("idx_pull_requests_repository_id", "pull_requests", ["repository_id"])
    op.create_index("idx_pull_requests_state", "pull_requests", ["state"])
    op.create_index("idx_pull_requests_head_sha", "pull_requests", ["head_sha"])

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pull_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("head_sha", sa.String(length=64), nullable=False),
        sa.Column("diff_hash", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("tokens_input", sa.Integer(), nullable=True),
        sa.Column("tokens_output", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("github_review_id", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("counts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["pull_request_id"],
            ["pull_requests.id"],
            name=op.f("fk_reviews_pull_request_id_pull_requests"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_reviews_repository_id_repositories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reviews")),
    )
    op.create_index("idx_reviews_pull_request_id", "reviews", ["pull_request_id"])
    op.create_index("idx_reviews_repository_id", "reviews", ["repository_id"])
    op.create_index("idx_reviews_status", "reviews", ["status"])
    op.create_index("idx_reviews_diff_hash", "reviews", ["diff_hash"])

    op.create_table(
        "review_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.Column("side", sa.String(length=8), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("github_comment_id", sa.BigInteger(), nullable=True),
        sa.Column("posted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
            name=op.f("fk_review_comments_review_id_reviews"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_comments")),
    )
    op.create_index("idx_review_comments_review_id", "review_comments", ["review_id"])
    op.create_index("idx_review_comments_severity", "review_comments", ["severity"])

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("queue", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("arq_job_id", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_kind", "jobs", ["kind"])
    op.create_index("idx_jobs_arq_job_id", "jobs", ["arq_job_id"])


def downgrade() -> None:
    op.drop_index("idx_jobs_arq_job_id", table_name="jobs")
    op.drop_index("idx_jobs_kind", table_name="jobs")
    op.drop_index("idx_jobs_status", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("idx_review_comments_severity", table_name="review_comments")
    op.drop_index("idx_review_comments_review_id", table_name="review_comments")
    op.drop_table("review_comments")

    op.drop_index("idx_reviews_diff_hash", table_name="reviews")
    op.drop_index("idx_reviews_status", table_name="reviews")
    op.drop_index("idx_reviews_repository_id", table_name="reviews")
    op.drop_index("idx_reviews_pull_request_id", table_name="reviews")
    op.drop_table("reviews")

    op.drop_index("idx_pull_requests_head_sha", table_name="pull_requests")
    op.drop_index("idx_pull_requests_state", table_name="pull_requests")
    op.drop_index("idx_pull_requests_repository_id", table_name="pull_requests")
    op.drop_table("pull_requests")

    op.drop_index(
        "idx_installation_repositories_repository_id",
        table_name="installation_repositories",
    )
    op.drop_index(
        "idx_installation_repositories_installation_id",
        table_name="installation_repositories",
    )
    op.drop_table("installation_repositories")

    op.drop_index("idx_repositories_owner", table_name="repositories")
    op.drop_index("idx_repositories_full_name", table_name="repositories")
    op.drop_table("repositories")

    op.drop_index("idx_github_installations_user_id", table_name="github_installations")
    op.drop_table("github_installations")

    op.drop_index("idx_users_github_login", table_name="users")
    op.drop_table("users")
