import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, ForeignKeyConstraint, Index, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.domain import TimestampMixin


class FormalKnowledgeMixin(TimestampMixin):
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_knowledge.id", ondelete="RESTRICT"), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def knowledge_constraints(prefix: str):
    return (
        UniqueConstraint("id", "user_id", "project_id", name=f"uq_{prefix}_scope"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name=f"ck_{prefix}_confidence"),
        CheckConstraint("status IN ('active', 'superseded', 'conflicted', 'archived')", name=f"ck_{prefix}_status"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name=f"ck_{prefix}_validity"),
    )


class KnowledgeEntity(FormalKnowledgeMixin, Base):
    __tablename__ = "knowledge_entities"
    __table_args__ = (
        *knowledge_constraints("entities"),
        Index("ix_entities_scope_type", "user_id", "project_id", "type"),
    )


class KnowledgeRelationship(FormalKnowledgeMixin, Base):
    __tablename__ = "knowledge_relationships"
    __table_args__ = (
        *knowledge_constraints("relationships"),
        ForeignKeyConstraint(["source_id", "user_id", "project_id"], ["knowledge_entities.id", "knowledge_entities.user_id", "knowledge_entities.project_id"], ondelete="RESTRICT", name="fk_relationship_source_scope"),
        ForeignKeyConstraint(["target_id", "user_id", "project_id"], ["knowledge_entities.id", "knowledge_entities.user_id", "knowledge_entities.project_id"], ondelete="RESTRICT", name="fk_relationship_target_scope"),
        Index("ix_relationships_source", "user_id", "project_id", "source_id"),
        Index("ix_relationships_target", "user_id", "project_id", "target_id"),
    )
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)


class KnowledgeEvidence(TimestampMixin, Base):
    __tablename__ = "knowledge_evidence"
    __table_args__ = (
        CheckConstraint("(entity_id IS NOT NULL AND relationship_id IS NULL) OR (entity_id IS NULL AND relationship_id IS NOT NULL)", name="ck_evidence_one_owner"),
        CheckConstraint("start_line >= 1 AND end_line >= start_line", name="ck_evidence_lines"),
        ForeignKeyConstraint(["entity_id", "user_id", "project_id"], ["knowledge_entities.id", "knowledge_entities.user_id", "knowledge_entities.project_id"], ondelete="CASCADE", name="fk_evidence_entity_scope"),
        ForeignKeyConstraint(["relationship_id", "user_id", "project_id"], ["knowledge_relationships.id", "knowledge_relationships.user_id", "knowledge_relationships.project_id"], ondelete="CASCADE", name="fk_evidence_relationship_scope"),
        Index("ix_evidence_entity", "entity_id"),
        Index("ix_evidence_relationship", "relationship_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_documents.id", ondelete="RESTRICT"), nullable=False)
    chunk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_chunks.id", ondelete="RESTRICT"), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    relationship_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(nullable=False)
    end_line: Mapped[int] = mapped_column(nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(JSON, nullable=False)
