"""Add project-scoped source repository identity."""

from alembic import op
import sqlalchemy as sa


revision = "20261019_0008"
down_revision = "20261019_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "source_repositories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name="fk_source_repositories_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('local_folder')",
            name="ck_source_repositories_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "project_id", "kind", "name",
            name="uq_source_repositories_scope_name",
        ),
    )
    op.create_index(
        "ix_source_repositories_user_id",
        "source_repositories",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_source_repositories_project_created",
        "source_repositories",
        ["project_id", "created_at"],
        unique=False,
    )
    with op.batch_alter_table("source_documents") as batch_op:
        batch_op.add_column(sa.Column("repository_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_source_documents_repository_id_source_repositories",
            "source_repositories",
            ["repository_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_source_documents_repository_id", ["repository_id"], unique=False
        )
        batch_op.create_index(
            "ix_sources_repository_dedupe",
            ["project_id", "repository_id", "source_type", "content_sha256"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("source_documents") as batch_op:
        batch_op.drop_index("ix_sources_repository_dedupe")
        batch_op.drop_index("ix_source_documents_repository_id")
        batch_op.drop_constraint(
            "fk_source_documents_repository_id_source_repositories",
            type_="foreignkey",
        )
        batch_op.drop_column("repository_id")
    op.drop_index(
        "ix_source_repositories_project_created",
        table_name="source_repositories",
    )
    op.drop_index(
        "ix_source_repositories_user_id",
        table_name="source_repositories",
    )
    op.drop_table("source_repositories")
