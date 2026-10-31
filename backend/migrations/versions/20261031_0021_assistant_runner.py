"""Explicit asynchronous assistant execution and durable read-only checkpoints."""
from alembic import op
import sqlalchemy as sa

revision = '20261031_0021'
down_revision = '20261031_0020'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('assistant_tasks') as batch:
        batch.drop_constraint('ck_assistant_tasks_status', type_='check')
        batch.create_check_constraint('ck_assistant_tasks_status', "status IN ('queued','running','succeeded','failed','interrupted','cancelled')")
        batch.add_column(sa.Column('execution_mode', sa.String(16), nullable=False, server_default='sync_v1'))
        batch.add_column(sa.Column('revision', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('elapsed_ms', sa.Integer(), nullable=False, server_default='0'))
    for name, extra, constraints in [
        ('assistant_attempts', [sa.Column('kind',sa.String(16),nullable=False),sa.Column('agent',sa.String(40),nullable=False),
            sa.Column('ordinal',sa.Integer(),nullable=False),sa.Column('status',sa.String(16),nullable=False)],
            [sa.UniqueConstraint('task_id','kind','ordinal',name='uq_assistant_attempt_ordinal'),
             sa.CheckConstraint("kind IN ('model','tool')",name='ck_assistant_attempt_kind'),
             sa.CheckConstraint("status IN ('started','succeeded','failed','unknown')",name='ck_assistant_attempt_status')]),
        ('assistant_steps',[sa.Column('sequence',sa.Integer(),nullable=False),sa.Column('kind',sa.String(16),nullable=False),
            sa.Column('state',sa.JSON(),nullable=False)],[sa.UniqueConstraint('task_id','sequence',name='uq_assistant_step_sequence')]),
        ('assistant_artifacts',[sa.Column('result',sa.JSON(),nullable=False)],[]),
        ('assistant_continuations',[sa.Column('input_sha256',sa.String(64),nullable=False)],[]),
    ]:
        op.create_table(name,sa.Column('id',sa.Uuid(),primary_key=True),
            sa.Column('task_id',sa.Uuid(),sa.ForeignKey('assistant_tasks.id',ondelete='CASCADE'),nullable=False),
            sa.Column('user_id',sa.Uuid(),nullable=False),
            sa.Column('project_id',sa.Uuid(),sa.ForeignKey('projects.id',ondelete='CASCADE'),nullable=False),
            *extra,sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
            sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),*constraints)
        op.create_index(f'ix_{name}_task_id',name,['task_id'])


def downgrade():
    # Downgrade is a maintenance operation: retain task results, close unsupported active states.
    op.execute("UPDATE assistant_tasks SET status='interrupted', execution_id=NULL, lease_until=NULL WHERE status IN ('queued','cancelled')")
    for name in ('assistant_continuations','assistant_artifacts','assistant_steps','assistant_attempts'):
        op.drop_index(f'ix_{name}_task_id',table_name=name)
        op.drop_table(name)
    with op.batch_alter_table('assistant_tasks') as batch:
        batch.drop_column('elapsed_ms'); batch.drop_column('revision'); batch.drop_column('execution_mode')
        batch.drop_constraint('ck_assistant_tasks_status',type_='check')
        batch.create_check_constraint('ck_assistant_tasks_status',"status IN ('running','succeeded','failed','interrupted')")
