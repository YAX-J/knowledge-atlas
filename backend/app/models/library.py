"""Library state and user feedback are separate from immutable evidence."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.domain import TimestampMixin


class SourceArchive(TimestampMixin, Base):
    __tablename__ = 'source_archives'
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('source_documents.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class AnswerFeedback(Base):
    __tablename__ = 'answer_feedback'
    __table_args__ = (
        CheckConstraint('claim_index >= 0 AND claim_index < 8', name='ck_feedback_claim_index'),
        CheckConstraint("category IN ('incorrect','irrelevant_citation','overstatement','wrong_version','incomplete')", name='ck_feedback_category'),
        Index('ix_feedback_turn_created', 'user_id', 'project_id', 'turn_id', 'created_at'),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    turn_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('conversation_turns.id', ondelete='CASCADE'), nullable=False)
    answer_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_index: Mapped[int] = mapped_column(nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
