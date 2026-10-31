"""M1 synchronous assistant envelope; not consumed by any background worker."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.domain import TimestampMixin


class AssistantTask(TimestampMixin, Base):
    __tablename__ = 'assistant_tasks'
    __table_args__ = (
        Index('ix_assistant_tasks_scope_created', 'user_id', 'project_id', 'created_at'),
        CheckConstraint("status IN ('running','succeeded','failed','interrupted')", name='ck_assistant_tasks_status'),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    request: Mapped[dict] = mapped_column(JSON, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON)
    events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    usage: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(100))
    execution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
