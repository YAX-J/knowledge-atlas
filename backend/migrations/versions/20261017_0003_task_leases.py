"""Add execution leases and attempt counters to processing tasks.

Revision ID: 20261017_0003
Revises: 20261017_0002
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261017_0003"
down_revision: str | None = "20261017_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("processing_tasks") as batch:
        batch.add_column(sa.Column("execution_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False))
        batch.create_check_constraint("ck_tasks_attempt_count", "attempt_count >= 0")
        batch.create_index("ix_tasks_user_queue", ["user_id", "status", "created_at"])


def downgrade() -> None:
    with op.batch_alter_table("processing_tasks") as batch:
        batch.drop_index("ix_tasks_user_queue")
        batch.drop_constraint("ck_tasks_attempt_count", type_="check")
        batch.drop_column("attempt_count")
        batch.drop_column("lease_expires_at")
        batch.drop_column("execution_id")
