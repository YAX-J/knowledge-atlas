"""Stable project notes, immutable revisions and source snapshot mappings."""
from alembic import op
import sqlalchemy as sa
revision='20261031_0022'
down_revision='20261031_0021'
branch_labels=None
depends_on=None


def stamps():
    return [sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False)]


def scope():
    return [sa.Column('user_id',sa.Uuid(),nullable=False),
        sa.Column('project_id',sa.Uuid(),sa.ForeignKey('projects.id',ondelete='CASCADE'),nullable=False)]


def upgrade():
    op.create_table('notes',sa.Column('id',sa.Uuid(),primary_key=True),*scope(),sa.Column('current_revision_id',sa.Uuid()),*stamps())
    op.create_index('ix_notes_scope_updated','notes',['user_id','project_id','updated_at'])
    op.create_table('note_revisions',sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('note_id',sa.Uuid(),sa.ForeignKey('notes.id',ondelete='CASCADE'),nullable=False),*scope(),
        sa.Column('number',sa.Integer(),nullable=False),sa.Column('parent_revision_id',sa.Uuid()),
        sa.Column('title',sa.String(120),nullable=False),sa.Column('markdown',sa.Text(),nullable=False),
        sa.Column('content_sha256',sa.String(64),nullable=False),sa.Column('origin',sa.String(16),nullable=False),
        sa.Column('task_id',sa.Uuid(),sa.ForeignKey('assistant_tasks.id',ondelete='SET NULL')),
        sa.Column('provenance',sa.JSON(),nullable=False),*stamps(),
        sa.UniqueConstraint('note_id','number',name='uq_note_revision_number'))
    op.create_index('ix_note_revisions_note_id','note_revisions',['note_id'])
    op.create_table('note_sources',sa.Column('revision_id',sa.Uuid(),sa.ForeignKey('note_revisions.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('source_id',sa.Uuid(),sa.ForeignKey('source_documents.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('parse_task_id',sa.Uuid(),sa.ForeignKey('processing_tasks.id',ondelete='RESTRICT'),nullable=False),*scope(),*stamps())


def downgrade():
    op.drop_table('note_sources');op.drop_index('ix_note_revisions_note_id',table_name='note_revisions')
    op.drop_table('note_revisions');op.drop_index('ix_notes_scope_updated',table_name='notes');op.drop_table('notes')
