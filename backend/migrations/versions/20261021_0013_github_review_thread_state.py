"""Add bounded GitHub Pull Request review thread snapshot metadata."""

from alembic import op
import sqlalchemy as sa


revision = "20261021_0013"
down_revision = "20261021_0012"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("github_pull_review_versions") as batch_op:
        batch_op.add_column(sa.Column(
            "review_threads_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ))
        batch_op.add_column(sa.Column(
            "resolved_review_threads_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ))
        batch_op.add_column(sa.Column(
            "review_threads_included",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ))
        batch_op.add_column(sa.Column(
            "review_threads_truncated",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ))
        batch_op.create_check_constraint(
            "ck_github_pull_review_versions_threads_count",
            "review_threads_count >= 0",
        )
        batch_op.create_check_constraint(
            "ck_github_pull_review_versions_resolved_threads_count",
            "resolved_review_threads_count >= 0 "
            "AND resolved_review_threads_count <= review_threads_count",
        )


def downgrade():
    with op.batch_alter_table("github_pull_review_versions") as batch_op:
        batch_op.drop_constraint(
            "ck_github_pull_review_versions_resolved_threads_count",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_github_pull_review_versions_threads_count",
            type_="check",
        )
        batch_op.drop_column("review_threads_truncated")
        batch_op.drop_column("review_threads_included")
        batch_op.drop_column("resolved_review_threads_count")
        batch_op.drop_column("review_threads_count")
