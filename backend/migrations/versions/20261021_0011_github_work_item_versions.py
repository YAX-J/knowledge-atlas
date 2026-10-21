"""Persist immutable GitHub Issue and Pull Request versions."""

from alembic import op
import sqlalchemy as sa


revision = "20261021_0011"
down_revision = "20261020_0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "github_work_item_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("provider_item_id", sa.String(length=255), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("html_url", sa.String(length=2048), nullable=False),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comments_count", sa.Integer(), nullable=False),
        sa.Column("comments_included", sa.Boolean(), nullable=False),
        sa.Column("comments_truncated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "item_type IN ('issue', 'pull_request')",
            name="ck_github_work_item_versions_type",
        ),
        sa.CheckConstraint(
            "state IN ('open', 'closed')",
            name="ck_github_work_item_versions_state",
        ),
        sa.CheckConstraint(
            "number >= 1", name="ck_github_work_item_versions_number"
        ),
        sa.CheckConstraint(
            "comments_count >= 0",
            name="ck_github_work_item_versions_comments_count",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_github_work_item_versions_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["source_repositories.id"],
            name="fk_github_work_item_versions_repository_id_source_repositories",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["source_documents.id"],
            name="fk_github_work_item_versions_source_id_source_documents",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["processing_tasks.id"],
            name="fk_github_work_item_versions_task_id_processing_tasks",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id", "provider_item_id", "provider_updated_at",
            "comments_included",
            name="uq_github_work_item_versions_provider_update",
        ),
    )
    op.create_index(
        "ix_github_work_item_versions_user_id",
        "github_work_item_versions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_github_work_item_versions_repository_number_updated",
        "github_work_item_versions",
        ["repository_id", "number", "provider_updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_github_work_item_versions_source",
        "github_work_item_versions",
        ["source_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_github_work_item_versions_source",
        table_name="github_work_item_versions",
    )
    op.drop_index(
        "ix_github_work_item_versions_repository_number_updated",
        table_name="github_work_item_versions",
    )
    op.drop_index(
        "ix_github_work_item_versions_user_id",
        table_name="github_work_item_versions",
    )
    op.drop_table("github_work_item_versions")
