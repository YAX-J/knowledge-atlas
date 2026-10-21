"""Persist immutable GitHub Pull Request review activity versions."""

from alembic import op
import sqlalchemy as sa


revision = "20261021_0012"
down_revision = "20261021_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "github_pull_review_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("provider_pull_id", sa.String(length=255), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("html_url", sa.String(length=2048), nullable=False),
        sa.Column("activity_digest", sa.String(length=64), nullable=False),
        sa.Column("reviews_count", sa.Integer(), nullable=False),
        sa.Column("review_comments_count", sa.Integer(), nullable=False),
        sa.Column("reviews_truncated", sa.Boolean(), nullable=False),
        sa.Column("review_comments_truncated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "number >= 1", name="ck_github_pull_review_versions_number"
        ),
        sa.CheckConstraint(
            "reviews_count >= 0",
            name="ck_github_pull_review_versions_reviews_count",
        ),
        sa.CheckConstraint(
            "review_comments_count >= 0",
            name="ck_github_pull_review_versions_comments_count",
        ),
        sa.CheckConstraint(
            "length(activity_digest) = 64",
            name="ck_github_pull_review_versions_digest",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_github_pull_review_versions_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["source_repositories.id"],
            name="fk_github_pull_review_versions_repository",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["source_documents.id"],
            name="fk_github_pull_review_versions_source_id_source_documents",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["processing_tasks.id"],
            name="fk_github_pull_review_versions_task_id_processing_tasks",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id", "provider_pull_id", "activity_digest",
            name="uq_github_pull_review_versions_activity",
        ),
    )
    op.create_index(
        "ix_github_pull_review_versions_user_id",
        "github_pull_review_versions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_github_pull_review_versions_repository_number_created",
        "github_pull_review_versions",
        ["repository_id", "number", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_github_pull_review_versions_source",
        "github_pull_review_versions",
        ["source_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_github_pull_review_versions_source",
        table_name="github_pull_review_versions",
    )
    op.drop_index(
        "ix_github_pull_review_versions_repository_number_created",
        table_name="github_pull_review_versions",
    )
    op.drop_index(
        "ix_github_pull_review_versions_user_id",
        table_name="github_pull_review_versions",
    )
    op.drop_table("github_pull_review_versions")
