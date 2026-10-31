"""Separate synchronous project assistant tasks, preserving legacy agent_runs."""
from alembic import op
import sqlalchemy as sa

revision = '20261031_0020'
down_revision = '20261029_0019'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('assistant_tasks',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('input_sha256', sa.String(64), nullable=False),
        sa.Column('request', sa.JSON(), nullable=False), sa.Column('result', sa.JSON()),
        sa.Column('events', sa.JSON(), nullable=False), sa.Column('usage', sa.JSON(), nullable=False),
        sa.Column('error_code', sa.String(100)), sa.Column('execution_id', sa.Uuid()),
        sa.Column('lease_until', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('running','succeeded','failed','interrupted')", name='ck_assistant_tasks_status'))
    op.create_index('ix_assistant_tasks_scope_created', 'assistant_tasks', ['user_id', 'project_id', 'created_at'])


def downgrade():
    op.drop_index('ix_assistant_tasks_scope_created', table_name='assistant_tasks')
    op.drop_table('assistant_tasks')
