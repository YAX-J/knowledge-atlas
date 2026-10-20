"""Persist repository commit snapshots and file provenance."""

from alembic import op
import sqlalchemy as sa


revision = "20261020_0010"
down_revision = "20261019_0009"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("source_repositories") as batch_op:
        batch_op.add_column(
            sa.Column("provider_repository_id", sa.String(length=255), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_source_repositories_provider_id_scope",
            ["user_id", "project_id", "provider", "provider_repository_id"],
        )

    op.create_table(
        "repository_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("ref", sa.String(length=255), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("tree_sha", sa.String(length=64), nullable=False),
        sa.Column("commit_url", sa.String(length=2048), nullable=True),
        sa.Column("commit_message", sa.Text(), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("deletion_detection_complete", sa.Boolean(), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("reused_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("renamed_count", sa.Integer(), nullable=False),
        sa.Column("deleted_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("downloaded_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provider IN ('github')", name="ck_repository_snapshots_provider"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_repository_snapshots_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["source_repositories.id"],
            name="fk_repository_snapshots_repository_id_source_repositories",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_repository_snapshots_user_id",
        "repository_snapshots",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_repository_snapshots_repository_ref_created",
        "repository_snapshots",
        ["repository_id", "ref", "created_at"],
        unique=False,
    )

    op.create_table(
        "repository_snapshot_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("previous_path", sa.String(length=1024), nullable=True),
        sa.Column("blob_sha", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('imported', 'reused', 'unchanged', 'renamed', "
            "'deleted', 'skipped')",
            name="ck_repository_snapshot_files_status",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["repository_snapshots.id"],
            name="fk_repository_snapshot_files_snapshot_id_repository_snapshots",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["source_documents.id"],
            name="fk_repository_snapshot_files_source_id_source_documents",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["processing_tasks.id"],
            name="fk_repository_snapshot_files_task_id_processing_tasks",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id", "path", name="uq_repository_snapshot_files_path"
        ),
    )
    op.create_index(
        "ix_repository_snapshot_files_snapshot_blob",
        "repository_snapshot_files",
        ["snapshot_id", "blob_sha"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_repository_snapshot_files_snapshot_blob",
        table_name="repository_snapshot_files",
    )
    op.drop_table("repository_snapshot_files")
    op.drop_index(
        "ix_repository_snapshots_repository_ref_created",
        table_name="repository_snapshots",
    )
    op.drop_index(
        "ix_repository_snapshots_user_id",
        table_name="repository_snapshots",
    )
    op.drop_table("repository_snapshots")
    with op.batch_alter_table("source_repositories") as batch_op:
        batch_op.drop_constraint(
            "uq_source_repositories_provider_id_scope", type_="unique"
        )
        batch_op.drop_column("provider_repository_id")
