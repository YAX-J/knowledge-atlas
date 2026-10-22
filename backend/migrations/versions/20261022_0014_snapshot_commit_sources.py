"""Link saved GitHub snapshots to explicit commit-message Markdown sources."""

from alembic import op
import sqlalchemy as sa

revision = "20261022_0014"
down_revision = "20261021_0013"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("repository_snapshots") as batch:
        batch.add_column(sa.Column("commit_source_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("commit_task_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_repository_snapshots_commit_source", "source_documents", ["commit_source_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_repository_snapshots_commit_task", "processing_tasks", ["commit_task_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_repository_snapshots_commit_source_id", ["commit_source_id"])


def downgrade():
    with op.batch_alter_table("repository_snapshots") as batch:
        batch.drop_index("ix_repository_snapshots_commit_source_id")
        batch.drop_constraint("fk_repository_snapshots_commit_task", type_="foreignkey")
        batch.drop_constraint("fk_repository_snapshots_commit_source", type_="foreignkey")
        batch.drop_column("commit_task_id")
        batch.drop_column("commit_source_id")
