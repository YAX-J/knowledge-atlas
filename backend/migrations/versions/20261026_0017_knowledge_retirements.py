"""Audited, non-destructive retirement of confirmed knowledge."""
from alembic import op
import sqlalchemy as sa

revision = '20261026_0017'
down_revision = '20261025_0016'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('knowledge_retirements',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('project_id', sa.Uuid(), nullable=False),
        sa.Column('entity_id', sa.Uuid()), sa.Column('relationship_id', sa.Uuid()),
        sa.Column('category', sa.String(20), nullable=False), sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('effective_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('before', sa.JSON(), nullable=False), sa.Column('after', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['entity_id', 'user_id', 'project_id'],
            ['knowledge_entities.id', 'knowledge_entities.user_id', 'knowledge_entities.project_id'],
            ondelete='RESTRICT', name='fk_retirements_entity_scope'),
        sa.ForeignKeyConstraint(['relationship_id', 'user_id', 'project_id'],
            ['knowledge_relationships.id', 'knowledge_relationships.user_id', 'knowledge_relationships.project_id'],
            ondelete='RESTRICT', name='fk_retirements_relationship_scope'),
        sa.CheckConstraint('(entity_id IS NOT NULL AND relationship_id IS NULL) OR '
            '(entity_id IS NULL AND relationship_id IS NOT NULL)', name='ck_retirements_one_owner'),
        sa.CheckConstraint("category IN ('correction', 'obsolete')", name='ck_retirements_category'))
    op.create_index('ix_retirements_scope_created', 'knowledge_retirements', ['user_id', 'project_id', 'effective_at'])


def downgrade():
    # Reopen no knowledge: rollback only removes this feature's audit table.
    op.drop_table('knowledge_retirements')
