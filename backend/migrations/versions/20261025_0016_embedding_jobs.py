"""Persist project-scoped index rebuild ownership and recovery status."""
from alembic import op
import sqlalchemy as sa

revision = '20261025_0016'
down_revision = '20261023_0015'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('embedding_jobs',
        sa.Column('project_id', sa.Uuid(), sa.ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('execution_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('result', sa.JSON()), sa.Column('error', sa.JSON()),
        sa.CheckConstraint("status IN ('running','succeeded','failed')", name='ck_embedding_jobs_status'))


def downgrade():
    op.drop_table('embedding_jobs')
