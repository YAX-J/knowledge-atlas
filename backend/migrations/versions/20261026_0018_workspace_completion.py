"""Audited identities, historical intervals and persistent conversations.

Revision ID: 20261026_0018
Revises: 20261026_0017
"""
from alembic import op
import sqlalchemy as sa

revision = '20261026_0018'
down_revision = '20261026_0017'
branch_labels = None
depends_on = None


def scoped(name, *columns):
    op.create_table(name,
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *columns)


def entity_fk(column, name):
    return sa.ForeignKeyConstraint([column, 'user_id', 'project_id'],
        ['knowledge_entities.id', 'knowledge_entities.user_id', 'knowledge_entities.project_id'],
        name=name, ondelete='RESTRICT')


def upgrade():
    op.add_column('repository_snapshots',sa.Column('scan_state',sa.JSON(),nullable=True))
    scoped('entity_aliases',
        sa.Column('entity_id', sa.Uuid(), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('normalized_name', sa.String(255), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        entity_fk('entity_id', 'fk_alias_entity_scope'),
        sa.UniqueConstraint('user_id', 'project_id', 'entity_type', 'normalized_name', name='uq_alias_name_scope'))
    scoped('entity_merges',
        sa.Column('source_id', sa.Uuid(), nullable=False), sa.Column('target_id', sa.Uuid(), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False), sa.Column('valid_to', sa.DateTime(timezone=True)),
        entity_fk('source_id', 'fk_merge_source_scope'), entity_fk('target_id', 'fk_merge_target_scope'),
        sa.CheckConstraint('source_id <> target_id', name='ck_merge_distinct'),
        sa.CheckConstraint('valid_to IS NULL OR valid_to >= valid_from', name='ck_merge_validity'))
    op.create_index('ix_merge_source_time', 'entity_merges', ['user_id', 'project_id', 'source_id', 'valid_from'])
    scoped('knowledge_periods',
        sa.Column('knowledge_id', sa.Uuid(), nullable=False), sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('entity', 'relationship')", name='ck_period_kind'),
        sa.CheckConstraint('valid_to >= valid_from', name='ck_period_validity'))
    op.create_index('ix_period_knowledge_time', 'knowledge_periods', ['user_id', 'project_id', 'knowledge_id', 'kind'])
    scoped('knowledge_operations', sa.Column('action', sa.String(30), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False), sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('before', sa.JSON(), nullable=False), sa.Column('after', sa.JSON(), nullable=False))
    op.create_index('ix_operation_scope_created', 'knowledge_operations', ['user_id', 'project_id', 'created_at'])
    scoped('conversations', sa.Column('title', sa.String(120), nullable=False),
        sa.Column('active_request_id', sa.Uuid()), sa.Column('lease_until', sa.DateTime(timezone=True)),
        sa.Column('active_execution_id', sa.Uuid()),
        sa.Column('archived', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('id', 'user_id', 'project_id', name='uq_conversation_scope'))
    scoped('conversation_turns', sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.Column('request_id', sa.Uuid(), nullable=False), sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False), sa.Column('retrieval_mode', sa.String(30), nullable=False),
        sa.Column('valid_at', sa.DateTime(timezone=True)), sa.Column('answer', sa.JSON()),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('error_code', sa.String(100)),
        sa.ForeignKeyConstraint(['conversation_id', 'user_id', 'project_id'],
            ['conversations.id', 'conversations.user_id', 'conversations.project_id'],
            name='fk_turn_conversation_scope', ondelete='CASCADE'),
        sa.UniqueConstraint('conversation_id', 'request_id', name='uq_turn_request'),
        sa.UniqueConstraint('conversation_id', 'position', name='uq_turn_position'),
        sa.CheckConstraint('position >= 1', name='ck_turn_position'))


def downgrade():
    op.drop_column('repository_snapshots','scan_state')
    for name in ('conversation_turns', 'conversations', 'knowledge_operations', 'knowledge_periods', 'entity_merges', 'entity_aliases'):
        op.drop_table(name)
