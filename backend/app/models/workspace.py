"""Audited identity/lifecycle changes and evidence-grounded conversations."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.domain import TimestampMixin


class ScopedRecord(TimestampMixin):
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)


class EntityAlias(ScopedRecord, Base):
    __tablename__ = 'entity_aliases'
    __table_args__ = (
        ForeignKeyConstraint(['entity_id', 'user_id', 'project_id'], ['knowledge_entities.id', 'knowledge_entities.user_id', 'knowledge_entities.project_id'], name='fk_alias_entity_scope', ondelete='RESTRICT'),
        UniqueConstraint('user_id', 'project_id', 'entity_type', 'normalized_name', name='uq_alias_name_scope'),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class EntityMerge(ScopedRecord, Base):
    __tablename__ = 'entity_merges'
    __table_args__ = (
        ForeignKeyConstraint(['source_id', 'user_id', 'project_id'], ['knowledge_entities.id', 'knowledge_entities.user_id', 'knowledge_entities.project_id'], name='fk_merge_source_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['target_id', 'user_id', 'project_id'], ['knowledge_entities.id', 'knowledge_entities.user_id', 'knowledge_entities.project_id'], name='fk_merge_target_scope', ondelete='RESTRICT'),
        CheckConstraint('source_id <> target_id', name='ck_merge_distinct'),
        CheckConstraint('valid_to IS NULL OR valid_to >= valid_from', name='ck_merge_validity'),
        Index('ix_merge_source_time', 'user_id', 'project_id', 'source_id', 'valid_from'),
    )
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgePeriod(ScopedRecord, Base):
    """Closed intervals saved before a human opens a new interval."""
    __tablename__ = 'knowledge_periods'
    __table_args__ = (
        CheckConstraint("kind IN ('entity', 'relationship')", name='ck_period_kind'),
        CheckConstraint('valid_to >= valid_from', name='ck_period_validity'),
        Index('ix_period_knowledge_time', 'user_id', 'project_id', 'knowledge_id', 'kind'),
    )
    knowledge_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class KnowledgeOperation(ScopedRecord, Base):
    __tablename__ = 'knowledge_operations'
    __table_args__ = (Index('ix_operation_scope_created', 'user_id', 'project_id', 'created_at'),)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    before: Mapped[dict] = mapped_column(JSON, nullable=False)
    after: Mapped[dict] = mapped_column(JSON, nullable=False)


class Conversation(ScopedRecord, Base):
    __tablename__ = 'conversations'
    __table_args__ = (UniqueConstraint('id', 'user_id', 'project_id', name='uq_conversation_scope'),)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    active_request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    active_execution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived: Mapped[bool] = mapped_column(default=False, nullable=False)


class ConversationTurn(ScopedRecord, Base):
    __tablename__ = 'conversation_turns'
    __table_args__ = (
        ForeignKeyConstraint(['conversation_id', 'user_id', 'project_id'], ['conversations.id', 'conversations.user_id', 'conversations.project_id'], name='fk_turn_conversation_scope', ondelete='CASCADE'),
        UniqueConstraint('conversation_id', 'request_id', name='uq_turn_request'),
        UniqueConstraint('conversation_id', 'position', name='uq_turn_position'),
        CheckConstraint('position >= 1', name='ck_turn_position'),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    valid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answer: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='running', nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
