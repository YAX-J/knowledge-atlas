"""Non-destructive library archiving and immutable answer feedback."""
from alembic import op
import sqlalchemy as sa

revision = '20261126_0024'
down_revision = '20261031_0023'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('source_archives',
        sa.Column('source_id', sa.Uuid(), sa.ForeignKey('source_documents.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('archived', sa.Boolean(), nullable=False), sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table('answer_feedback', sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('turn_id', sa.Uuid(), sa.ForeignKey('conversation_turns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('answer_sha256', sa.String(64), nullable=False), sa.Column('claim_index', sa.Integer(), nullable=False),
        sa.Column('claim_text', sa.Text(), nullable=False), sa.Column('category', sa.String(30), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('claim_index >= 0 AND claim_index < 8', name='ck_feedback_claim_index'),
        sa.CheckConstraint("category IN ('incorrect','irrelevant_citation','overstatement','wrong_version','incomplete')", name='ck_feedback_category'))
    op.create_index('ix_feedback_turn_created', 'answer_feedback', ['user_id','project_id','turn_id','created_at'])


def downgrade():
    op.drop_index('ix_feedback_turn_created', table_name='answer_feedback')
    op.drop_table('answer_feedback')
    op.drop_table('source_archives')
