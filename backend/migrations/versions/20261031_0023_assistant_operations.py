"""Version-bound human-reviewed assistant operations and immutable approvals."""
from alembic import op
import sqlalchemy as sa
revision='20261031_0023'
down_revision='20261031_0022'
branch_labels=None
depends_on=None


def upgrade():
    with op.batch_alter_table('assistant_tasks') as batch:
        batch.drop_constraint('ck_assistant_tasks_status',type_='check')
        batch.create_check_constraint('ck_assistant_tasks_status',"status IN ('queued','running','waiting_approval','succeeded','failed','interrupted','cancelled')")
    for name,extra in [
        ('assistant_operations',[sa.Column('kind',sa.String(50),nullable=False),sa.Column('input_sha256',sa.String(64),nullable=False),
            sa.Column('proposal_sha256',sa.String(64),nullable=False),sa.Column('payload',sa.JSON(),nullable=False),
            sa.Column('status',sa.String(20),nullable=False),sa.Column('result',sa.JSON()),sa.Column('error_code',sa.String(100))]),
        ('assistant_approvals',[sa.Column('operation_id',sa.Uuid(),sa.ForeignKey('assistant_operations.id',ondelete='CASCADE'),nullable=False),
            sa.Column('input_sha256',sa.String(64),nullable=False),sa.Column('decision',sa.String(16),nullable=False)])]:
        op.create_table(name,sa.Column('id',sa.Uuid(),primary_key=True),
            sa.Column('task_id',sa.Uuid(),sa.ForeignKey('assistant_tasks.id',ondelete='CASCADE'),nullable=False),
            sa.Column('user_id',sa.Uuid(),nullable=False),sa.Column('project_id',sa.Uuid(),sa.ForeignKey('projects.id',ondelete='CASCADE'),nullable=False),
            *extra,sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
            sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_assistant_operations_task','assistant_operations',['task_id','created_at'])
    op.create_index('ix_assistant_approvals_operation_id','assistant_approvals',['operation_id'])


def downgrade():
    op.execute("UPDATE assistant_tasks SET status='interrupted',execution_id=NULL,lease_until=NULL,revision=revision+1 WHERE status='waiting_approval' OR (execution_mode='async_v3' AND status IN ('queued','running'))")
    op.drop_index('ix_assistant_approvals_operation_id',table_name='assistant_approvals');op.drop_table('assistant_approvals')
    op.drop_index('ix_assistant_operations_task',table_name='assistant_operations');op.drop_table('assistant_operations')
    with op.batch_alter_table('assistant_tasks') as batch:
        batch.drop_constraint('ck_assistant_tasks_status',type_='check')
        batch.create_check_constraint('ck_assistant_tasks_status',"status IN ('queued','running','succeeded','failed','interrupted','cancelled')")
