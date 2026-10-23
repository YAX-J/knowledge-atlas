"""Human-reviewed cross-source evolution; never populated by an LLM directly."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.domain import TimestampMixin


class KnowledgeChange(TimestampMixin, Base):
    __tablename__ = "knowledge_changes"
    __table_args__ = (
        ForeignKeyConstraint(["new_entity_id", "user_id", "project_id"],
                             ["knowledge_entities.id", "knowledge_entities.user_id", "knowledge_entities.project_id"],
                             ondelete="RESTRICT", name="fk_changes_new_scope"),
        ForeignKeyConstraint(["old_entity_id", "user_id", "project_id"],
                             ["knowledge_entities.id", "knowledge_entities.user_id", "knowledge_entities.project_id"],
                             ondelete="RESTRICT", name="fk_changes_old_scope"),
        CheckConstraint("new_entity_id <> old_entity_id", name="ck_changes_distinct"),
        CheckConstraint("kind IN ('SUPERSEDES', 'SUPPLEMENTS', 'CONFLICTS_WITH')", name="ck_changes_kind"),
        CheckConstraint("review_status IN ('pending', 'confirmed', 'rejected')", name="ck_changes_review"),
        CheckConstraint("(review_status = 'pending' AND resolved_at IS NULL) OR "
                        "(review_status <> 'pending' AND resolved_at IS NOT NULL)", name="ck_changes_resolution"),
        Index("ix_changes_scope_review", "user_id", "project_id", "review_status"),
        Index("ix_changes_new", "user_id", "project_id", "new_entity_id"),
        Index("ix_changes_old", "user_id", "project_id", "old_entity_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    new_entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    old_entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_evidence.id", ondelete="RESTRICT"), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Immutable resolution snapshots: both endpoints, time intervals and statuses.
    before: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    after: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
