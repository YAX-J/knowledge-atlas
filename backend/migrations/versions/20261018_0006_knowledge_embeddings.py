"""Add semantic embeddings for formal knowledge entities."""

from alembic import op
from pgvector.sqlalchemy import VECTOR
import sqlalchemy as sa


revision = "20261018_0006"
down_revision = "20261017_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "knowledge_embeddings",
        sa.Column("entity_id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("embedding", VECTOR(1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["entity_id", "user_id", "project_id"],
            ["knowledge_entities.id", "knowledge_entities.user_id", "knowledge_entities.project_id"],
            ondelete="CASCADE", name="fk_embedding_entity_scope",
        ),
        sa.CheckConstraint("dimensions = 1024", name="ck_embeddings_dimensions"),
    )
    op.create_index(
        "ix_embeddings_scope_model", "knowledge_embeddings", ["user_id", "project_id", "model"]
    )


def downgrade():
    op.drop_table("knowledge_embeddings")
