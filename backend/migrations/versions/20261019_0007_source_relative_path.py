"""Persist optional folder-relative paths for uploaded sources."""

from alembic import op
import sqlalchemy as sa


revision = "20261019_0007"
down_revision = "20261018_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "source_documents",
        sa.Column("relative_path", sa.String(length=1024), nullable=True),
    )


def downgrade():
    with op.batch_alter_table("source_documents") as batch_op:
        batch_op.drop_column("relative_path")
