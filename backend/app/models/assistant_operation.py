"""Immutable scoped proposals, exact decisions and operation receipts."""
import uuid
from sqlalchemy import ForeignKey, Index, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.domain import TimestampMixin


class AssistantOperation(TimestampMixin,Base):
    __tablename__='assistant_operations'
    __table_args__=(Index('ix_assistant_operations_task','task_id','created_at'),)
    id:Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True)
    task_id:Mapped[uuid.UUID]=mapped_column(ForeignKey('assistant_tasks.id',ondelete='CASCADE'),nullable=False)
    user_id:Mapped[uuid.UUID]=mapped_column(Uuid,nullable=False)
    project_id:Mapped[uuid.UUID]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),nullable=False)
    kind:Mapped[str]=mapped_column(String(50),nullable=False)
    input_sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    proposal_sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    payload:Mapped[dict]=mapped_column(JSON,nullable=False)
    status:Mapped[str]=mapped_column(String(20),nullable=False)
    result:Mapped[dict|None]=mapped_column(JSON)
    error_code:Mapped[str|None]=mapped_column(String(100))


class AssistantApproval(TimestampMixin,Base):
    __tablename__='assistant_approvals'
    id:Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True)
    operation_id:Mapped[uuid.UUID]=mapped_column(ForeignKey('assistant_operations.id',ondelete='CASCADE'),nullable=False,index=True)
    task_id:Mapped[uuid.UUID]=mapped_column(ForeignKey('assistant_tasks.id',ondelete='CASCADE'),nullable=False)
    user_id:Mapped[uuid.UUID]=mapped_column(Uuid,nullable=False)
    project_id:Mapped[uuid.UUID]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),nullable=False)
    input_sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    decision:Mapped[str]=mapped_column(String(16),nullable=False)
