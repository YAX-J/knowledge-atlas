"""Scoped synchronous-v1/queued-v2 assistant tasks and durable execution receipts."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.domain import TimestampMixin


class AssistantTask(TimestampMixin, Base):
    __tablename__ = 'assistant_tasks'
    __table_args__ = (
        Index('ix_assistant_tasks_scope_created', 'user_id', 'project_id', 'created_at'),
        CheckConstraint("status IN ('queued','running','succeeded','failed','interrupted','cancelled')", name='ck_assistant_tasks_status'),
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
    execution_mode: Mapped[str] = mapped_column(String(16), default='sync_v1', server_default='sync_v1', nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default='0', nullable=False)
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0, server_default='0', nullable=False)


class AssistantAttempt(TimestampMixin, Base):
    __tablename__ = 'assistant_attempts'
    __table_args__ = (UniqueConstraint('task_id', 'kind', 'ordinal', name='uq_assistant_attempt_ordinal'),
        CheckConstraint("kind IN ('model','tool')", name='ck_assistant_attempt_kind'),
        CheckConstraint("status IN ('started','succeeded','failed','unknown')", name='ck_assistant_attempt_status'),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('assistant_tasks.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    agent: Mapped[str] = mapped_column(String(40), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class AssistantStep(TimestampMixin, Base):
    __tablename__ = 'assistant_steps'
    __table_args__ = (UniqueConstraint('task_id', 'sequence', name='uq_assistant_step_sequence'),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('assistant_tasks.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[dict] = mapped_column(JSON, nullable=False)


class AssistantArtifact(TimestampMixin, Base):
    __tablename__ = 'assistant_artifacts'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('assistant_tasks.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)


class AssistantContinuation(TimestampMixin, Base):
    __tablename__ = 'assistant_continuations'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('assistant_tasks.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
