"""Add normalized GitHub identity to source repositories."""

from alembic import op
import sqlalchemy as sa


revision = "20261019_0009"
down_revision = "20261019_0008"
branch_labels = None
depends_on = None


REMOTE_IDENTITY_CHECK = (
    "(kind = 'local_folder' AND provider IS NULL "
    "AND remote_owner IS NULL AND remote_name IS NULL "
    "AND remote_url IS NULL) OR "
    "(provider = 'github' AND remote_owner IS NOT NULL "
    "AND remote_name IS NOT NULL AND remote_url IS NOT NULL)"
)


def upgrade():
    with op.batch_alter_table("source_repositories") as batch_op:
        batch_op.drop_constraint(
            "ck_source_repositories_kind", type_="check"
        )
        batch_op.add_column(sa.Column("provider", sa.String(length=30), nullable=True))
        batch_op.add_column(
            sa.Column("remote_owner", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("remote_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("remote_url", sa.String(length=1024), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_source_repositories_kind",
            "kind IN ('local_folder', 'git_remote')",
        )
        batch_op.create_check_constraint(
            "ck_source_repositories_remote_identity",
            REMOTE_IDENTITY_CHECK,
        )
        batch_op.create_unique_constraint(
            "uq_source_repositories_remote_scope",
            ["user_id", "project_id", "provider", "remote_owner", "remote_name"],
        )


def downgrade():
    op.execute("DELETE FROM source_repositories WHERE kind = 'git_remote'")
    with op.batch_alter_table("source_repositories") as batch_op:
        batch_op.drop_constraint(
            "uq_source_repositories_remote_scope", type_="unique"
        )
        batch_op.drop_constraint(
            "ck_source_repositories_remote_identity", type_="check"
        )
        batch_op.drop_constraint(
            "ck_source_repositories_kind", type_="check"
        )
        batch_op.drop_column("remote_url")
        batch_op.drop_column("remote_name")
        batch_op.drop_column("remote_owner")
        batch_op.drop_column("provider")
        batch_op.create_check_constraint(
            "ck_source_repositories_kind",
            "kind IN ('local_folder')",
        )
