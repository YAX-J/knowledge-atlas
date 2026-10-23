"""Reviewed cross-source knowledge evolution and resolution audit."""
from alembic import op
import sqlalchemy as sa

revision = "20261023_0015"
down_revision = "20261022_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "knowledge_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("new_entity_id", sa.Uuid(), nullable=False),
        sa.Column("old_entity_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_status", sa.String(20), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["knowledge_evidence.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["new_entity_id", "user_id", "project_id"],
                                ["knowledge_entities.id", "knowledge_entities.user_id", "knowledge_entities.project_id"],
                                ondelete="RESTRICT", name="fk_changes_new_scope"),
        sa.ForeignKeyConstraint(["old_entity_id", "user_id", "project_id"],
                                ["knowledge_entities.id", "knowledge_entities.user_id", "knowledge_entities.project_id"],
                                ondelete="RESTRICT", name="fk_changes_old_scope"),
        sa.CheckConstraint("new_entity_id <> old_entity_id", name="ck_changes_distinct"),
        sa.CheckConstraint("kind IN ('SUPERSEDES', 'SUPPLEMENTS', 'CONFLICTS_WITH')", name="ck_changes_kind"),
        sa.CheckConstraint("review_status IN ('pending', 'confirmed', 'rejected')", name="ck_changes_review"),
        sa.CheckConstraint("(review_status = 'pending' AND resolved_at IS NULL) OR "
                           "(review_status <> 'pending' AND resolved_at IS NOT NULL)", name="ck_changes_resolution"),
    )
    op.create_index("ix_changes_scope_review", "knowledge_changes", ["user_id", "project_id", "review_status"])
    op.create_index("ix_changes_new", "knowledge_changes", ["user_id", "project_id", "new_entity_id"])
    op.create_index("ix_changes_old", "knowledge_changes", ["user_id", "project_id", "old_entity_id"])


def downgrade():
    op.drop_table("knowledge_changes")
