"""Add formal knowledge entities, relationships, and evidence."""

from alembic import op
import sqlalchemy as sa

revision = "20261017_0005"
down_revision = "20261017_0004"
branch_labels = None
depends_on = None


def columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("candidate_knowledge.id", ondelete="RESTRICT"), unique=True, nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def constraints(prefix):
    return [
        sa.UniqueConstraint("id", "user_id", "project_id", name=f"uq_{prefix}_scope"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name=f"ck_{prefix}_confidence"),
        sa.CheckConstraint("status IN ('active', 'superseded', 'conflicted', 'archived')", name=f"ck_{prefix}_status"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name=f"ck_{prefix}_validity"),
    ]


def upgrade():
    op.create_table("knowledge_entities", *columns(), *constraints("entities"))
    op.create_index("ix_entities_scope_type", "knowledge_entities", ["user_id", "project_id", "type"])
    op.create_table(
        "knowledge_relationships", *columns(), *constraints("relationships"),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["source_id", "user_id", "project_id"], ["knowledge_entities.id", "knowledge_entities.user_id", "knowledge_entities.project_id"], ondelete="RESTRICT", name="fk_relationship_source_scope"),
        sa.ForeignKeyConstraint(["target_id", "user_id", "project_id"], ["knowledge_entities.id", "knowledge_entities.user_id", "knowledge_entities.project_id"], ondelete="RESTRICT", name="fk_relationship_target_scope"),
    )
    for side in ("source", "target"):
        op.create_index(f"ix_relationships_{side}", "knowledge_relationships", ["user_id", "project_id", f"{side}_id"])
    op.create_table(
        "knowledge_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("source_documents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("source_chunks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("entity_id", sa.Uuid()), sa.Column("relationship_id", sa.Uuid()),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False), sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("heading_path", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("(entity_id IS NOT NULL AND relationship_id IS NULL) OR (entity_id IS NULL AND relationship_id IS NOT NULL)", name="ck_evidence_one_owner"),
        sa.CheckConstraint("start_line >= 1 AND end_line >= start_line", name="ck_evidence_lines"),
        sa.ForeignKeyConstraint(["entity_id", "user_id", "project_id"], ["knowledge_entities.id", "knowledge_entities.user_id", "knowledge_entities.project_id"], ondelete="CASCADE", name="fk_evidence_entity_scope"),
        sa.ForeignKeyConstraint(["relationship_id", "user_id", "project_id"], ["knowledge_relationships.id", "knowledge_relationships.user_id", "knowledge_relationships.project_id"], ondelete="CASCADE", name="fk_evidence_relationship_scope"),
    )
    op.create_index("ix_evidence_entity", "knowledge_evidence", ["entity_id"])
    op.create_index("ix_evidence_relationship", "knowledge_evidence", ["relationship_id"])


def downgrade():
    op.drop_table("knowledge_evidence")
    op.drop_table("knowledge_relationships")
    op.drop_table("knowledge_entities")
