"""Persist line-addressable Markdown chunks.

Revision ID: 20261017_0002
Revises: 20261017_0001
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261017_0002"
down_revision: str | None = "20261017_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("heading_path", sa.JSON(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["source_documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("source_id", "position", name="uq_chunks_source_position"),
        sa.CheckConstraint("position >= 0", name="ck_chunks_position"),
        sa.CheckConstraint(
            "start_line >= 1 AND end_line >= start_line", name="ck_chunks_lines"
        ),
    )
    op.create_index(
        "ix_chunks_user_project_source", "source_chunks",
        ["user_id", "project_id", "source_id"],
    )


def downgrade() -> None:
    op.drop_table("source_chunks")
