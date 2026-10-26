"""Immutable snapshots of explicit human knowledge retirement."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeRetirement(Base):
    __tablename__ = 'knowledge_retirements'
    __table_args__ = (
        ForeignKeyConstraint(['entity_id', 'user_id', 'project_id'],
            ['knowledge_entities.id', 'knowledge_entities.user_id', 'knowledge_entities.project_id'],
            ondelete='RESTRICT', name='fk_retirements_entity_scope'),
        ForeignKeyConstraint(['relationship_id', 'user_id', 'project_id'],
            ['knowledge_relationships.id', 'knowledge_relationships.user_id', 'knowledge_relationships.project_id'],
            ondelete='RESTRICT', name='fk_retirements_relationship_scope'),
        CheckConstraint('(entity_id IS NOT NULL AND relationship_id IS NULL) OR '
            '(entity_id IS NULL AND relationship_id IS NOT NULL)', name='ck_retirements_one_owner'),
        CheckConstraint("category IN ('correction', 'obsolete')", name='ck_retirements_category'),
        Index('ix_retirements_scope_created', 'user_id', 'project_id', 'effective_at'),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    relationship_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    before: Mapped[dict] = mapped_column(JSON, nullable=False)
    after: Mapped[dict] = mapped_column(JSON, nullable=False)
