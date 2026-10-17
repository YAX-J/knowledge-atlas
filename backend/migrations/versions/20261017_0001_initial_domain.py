"""Create project, source, task, and candidate knowledge tables.

Revision ID: 20261017_0001
Revises:
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261017_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index(
        "ix_projects_user_created", "projects", ["user_id", "created_at"]
    )

    op.create_table(
        "source_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "uploaded",
                "processing",
                "ready",
                "failed",
                name="source_status",
                native_enum=False,
                length=20,
            ),
            server_default="uploaded",
            nullable=False,
        ),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_documents_user_id", "source_documents", ["user_id"])
    op.create_index(
        "ix_sources_project_created",
        "source_documents",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_sources_project_sha256",
        "source_documents",
        ["project_id", "content_sha256"],
    )

    op.create_table(
        "processing_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="task_status",
                native_enum=False,
                length=20,
            ),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("stage", sa.String(length=50), server_default="uploaded", nullable=False),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["source_documents.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100", name="ck_tasks_progress_range"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processing_tasks_user_id", "processing_tasks", ["user_id"])
    op.create_index(
        "ix_tasks_project_status", "processing_tasks", ["project_id", "status"]
    )

    op.create_table(
        "candidate_knowledge",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("payload", sa.JSON(), server_default="{}", nullable=False),
        sa.Column(
            "review_status",
            sa.Enum(
                "pending",
                "confirmed",
                "rejected",
                name="review_status",
                native_enum=False,
                length=20,
            ),
            server_default="pending",
            nullable=False,
        ),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["source_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["processing_tasks.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_candidates_confidence_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidate_knowledge_user_id", "candidate_knowledge", ["user_id"])
    op.create_index(
        "ix_candidates_project_review",
        "candidate_knowledge",
        ["project_id", "review_status"],
    )


def downgrade() -> None:
    op.drop_table("candidate_knowledge")
    op.drop_table("processing_tasks")
    op.drop_table("source_documents")
    op.drop_table("projects")

