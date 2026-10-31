"""Stable notes and append-only revisions; imported sources are separate snapshots."""
import uuid
from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.domain import TimestampMixin


class Note(TimestampMixin,Base):
    __tablename__='notes'
    __table_args__=(Index('ix_notes_scope_updated','user_id','project_id','updated_at'),)
    id:Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True)
    user_id:Mapped[uuid.UUID]=mapped_column(Uuid,nullable=False)
    project_id:Mapped[uuid.UUID]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),nullable=False)
    current_revision_id:Mapped[uuid.UUID|None]=mapped_column(Uuid)


class NoteRevision(TimestampMixin,Base):
    __tablename__='note_revisions'
    __table_args__=(UniqueConstraint('note_id','number',name='uq_note_revision_number'),)
    id:Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True)
    note_id:Mapped[uuid.UUID]=mapped_column(ForeignKey('notes.id',ondelete='CASCADE'),nullable=False,index=True)
    user_id:Mapped[uuid.UUID]=mapped_column(Uuid,nullable=False)
    project_id:Mapped[uuid.UUID]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),nullable=False)
    number:Mapped[int]=mapped_column(Integer,nullable=False)
    parent_revision_id:Mapped[uuid.UUID|None]=mapped_column(Uuid)
    title:Mapped[str]=mapped_column(String(120),nullable=False)
    markdown:Mapped[str]=mapped_column(Text,nullable=False)
    content_sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    origin:Mapped[str]=mapped_column(String(16),nullable=False)
    task_id:Mapped[uuid.UUID|None]=mapped_column(ForeignKey('assistant_tasks.id',ondelete='SET NULL'))
    provenance:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)


class NoteSource(TimestampMixin,Base):
    __tablename__='note_sources'
    revision_id:Mapped[uuid.UUID]=mapped_column(ForeignKey('note_revisions.id',ondelete='CASCADE'),primary_key=True)
    source_id:Mapped[uuid.UUID]=mapped_column(ForeignKey('source_documents.id',ondelete='RESTRICT'),nullable=False)
    parse_task_id:Mapped[uuid.UUID]=mapped_column(ForeignKey('processing_tasks.id',ondelete='RESTRICT'),nullable=False)
    user_id:Mapped[uuid.UUID]=mapped_column(Uuid,nullable=False)
    project_id:Mapped[uuid.UUID]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),nullable=False)
