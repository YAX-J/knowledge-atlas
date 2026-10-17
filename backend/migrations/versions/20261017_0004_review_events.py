"""Persist candidate review decisions and their before/after values."""

from alembic import op
import sqlalchemy as sa


revision = "20261017_0004"
down_revision = "20261017_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_knowledge.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.CheckConstraint("action IN ('confirm', 'reject')", name="ck_review_events_action"),
    )
    op.create_index("ix_review_events_candidate", "review_events", ["candidate_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_review_events_candidate", table_name="review_events")
    op.drop_table("review_events")
