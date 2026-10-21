import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SourceStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sources: Mapped[list["SourceDocument"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["ProcessingTask"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    candidates: Mapped[list["CandidateKnowledge"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    repositories: Mapped[list["SourceRepository"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class SourceRepository(TimestampMixin, Base):
    __tablename__ = "source_repositories"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('local_folder', 'git_remote')",
            name="ck_source_repositories_kind",
        ),
        CheckConstraint(
            "(kind = 'local_folder' AND provider IS NULL "
            "AND remote_owner IS NULL AND remote_name IS NULL "
            "AND remote_url IS NULL) OR "
            "(provider = 'github' AND remote_owner IS NOT NULL "
            "AND remote_name IS NOT NULL AND remote_url IS NOT NULL)",
            name="ck_source_repositories_remote_identity",
        ),
        UniqueConstraint(
            "user_id", "project_id", "kind", "name",
            name="uq_source_repositories_scope_name",
        ),
        UniqueConstraint(
            "user_id", "project_id", "provider", "remote_owner", "remote_name",
            name="uq_source_repositories_remote_scope",
        ),
        UniqueConstraint(
            "user_id", "project_id", "provider", "provider_repository_id",
            name="uq_source_repositories_provider_id_scope",
        ),
        Index(
            "ix_source_repositories_project_created", "project_id", "created_at"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(
        String(30), default="local_folder", nullable=False
    )
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    remote_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    provider_repository_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="repositories")
    sources: Mapped[list["SourceDocument"]] = relationship(
        back_populates="repository"
    )
    snapshots: Mapped[list["RepositorySnapshot"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    work_item_versions: Mapped[list["GithubWorkItemVersion"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    pull_review_versions: Mapped[list["GithubPullReviewVersion"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class RepositorySnapshot(TimestampMixin, Base):
    __tablename__ = "repository_snapshots"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('github')", name="ck_repository_snapshots_provider"
        ),
        Index(
            "ix_repository_snapshots_repository_ref_created",
            "repository_id", "ref", "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_repositories.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    ref: Mapped[str] = mapped_column(String(255), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    tree_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    commit_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    commit_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deletion_detection_complete: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    file_count: Mapped[int] = mapped_column(default=0, nullable=False)
    imported_count: Mapped[int] = mapped_column(default=0, nullable=False)
    reused_count: Mapped[int] = mapped_column(default=0, nullable=False)
    unchanged_count: Mapped[int] = mapped_column(default=0, nullable=False)
    renamed_count: Mapped[int] = mapped_column(default=0, nullable=False)
    deleted_count: Mapped[int] = mapped_column(default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(default=0, nullable=False)
    downloaded_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    repository: Mapped[SourceRepository] = relationship(back_populates="snapshots")
    files: Mapped[list["RepositorySnapshotFile"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


class RepositorySnapshotFile(TimestampMixin, Base):
    __tablename__ = "repository_snapshot_files"
    __table_args__ = (
        CheckConstraint(
            "status IN ('imported', 'reused', 'unchanged', 'renamed', "
            "'deleted', 'skipped')",
            name="ck_repository_snapshot_files_status",
        ),
        UniqueConstraint(
            "snapshot_id", "path", name="uq_repository_snapshot_files_path"
        ),
        Index(
            "ix_repository_snapshot_files_snapshot_blob",
            "snapshot_id", "blob_sha",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("processing_tasks.id", ondelete="SET NULL"), nullable=True
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    previous_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    blob_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)

    snapshot: Mapped[RepositorySnapshot] = relationship(back_populates="files")


class GithubWorkItemVersion(TimestampMixin, Base):
    __tablename__ = "github_work_item_versions"
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('issue', 'pull_request')",
            name="ck_github_work_item_versions_type",
        ),
        CheckConstraint(
            "state IN ('open', 'closed')",
            name="ck_github_work_item_versions_state",
        ),
        CheckConstraint("number >= 1", name="ck_github_work_item_versions_number"),
        CheckConstraint(
            "comments_count >= 0", name="ck_github_work_item_versions_comments_count"
        ),
        UniqueConstraint(
            "repository_id", "provider_item_id", "provider_updated_at",
            "comments_included",
            name="uq_github_work_item_versions_provider_update",
        ),
        Index(
            "ix_github_work_item_versions_repository_number_updated",
            "repository_id", "number", "provider_updated_at",
        ),
        Index("ix_github_work_item_versions_source", "source_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_repositories.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("processing_tasks.id", ondelete="SET NULL"), nullable=True
    )
    provider_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    number: Mapped[int] = mapped_column(nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    html_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    provider_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    comments_count: Mapped[int] = mapped_column(default=0, nullable=False)
    comments_included: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    comments_truncated: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    repository: Mapped[SourceRepository] = relationship(
        back_populates="work_item_versions"
    )


class GithubPullReviewVersion(TimestampMixin, Base):
    __tablename__ = "github_pull_review_versions"
    __table_args__ = (
        CheckConstraint("number >= 1", name="ck_github_pull_review_versions_number"),
        CheckConstraint(
            "reviews_count >= 0",
            name="ck_github_pull_review_versions_reviews_count",
        ),
        CheckConstraint(
            "review_comments_count >= 0",
            name="ck_github_pull_review_versions_comments_count",
        ),
        CheckConstraint(
            "review_threads_count >= 0",
            name="ck_github_pull_review_versions_threads_count",
        ),
        CheckConstraint(
            "resolved_review_threads_count >= 0 "
            "AND resolved_review_threads_count <= review_threads_count",
            name="ck_github_pull_review_versions_resolved_threads_count",
        ),
        CheckConstraint(
            "length(activity_digest) = 64",
            name="ck_github_pull_review_versions_digest",
        ),
        UniqueConstraint(
            "repository_id", "provider_pull_id", "activity_digest",
            name="uq_github_pull_review_versions_activity",
        ),
        Index(
            "ix_github_pull_review_versions_repository_number_created",
            "repository_id", "number", "created_at",
        ),
        Index("ix_github_pull_review_versions_source", "source_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_repositories.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("processing_tasks.id", ondelete="SET NULL"), nullable=True
    )
    provider_pull_id: Mapped[str] = mapped_column(String(255), nullable=False)
    number: Mapped[int] = mapped_column(nullable=False)
    html_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    activity_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    reviews_count: Mapped[int] = mapped_column(default=0, nullable=False)
    review_comments_count: Mapped[int] = mapped_column(default=0, nullable=False)
    reviews_truncated: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    review_comments_truncated: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    review_threads_count: Mapped[int] = mapped_column(
        default=0, server_default="0", nullable=False
    )
    resolved_review_threads_count: Mapped[int] = mapped_column(
        default=0, server_default="0", nullable=False
    )
    review_threads_included: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    review_threads_truncated: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    repository: Mapped[SourceRepository] = relationship(
        back_populates="pull_review_versions"
    )


class SourceDocument(TimestampMixin, Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        Index("ix_sources_project_created", "project_id", "created_at"),
        Index("ix_sources_project_sha256", "project_id", "content_sha256"),
        Index(
            "ix_sources_repository_dedupe",
            "project_id",
            "repository_id",
            "source_type",
            "content_sha256",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_repositories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SourceStatus] = mapped_column(
        SAEnum(
            SourceStatus,
            values_callable=lambda items: [item.value for item in items],
            native_enum=False,
            length=20,
        ),
        default=SourceStatus.UPLOADED,
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="sources")
    repository: Mapped[SourceRepository | None] = relationship(
        back_populates="sources"
    )
    chunks: Mapped[list["SourceChunk"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["ProcessingTask"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    candidates: Mapped[list["CandidateKnowledge"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class SourceChunk(TimestampMixin, Base):
    __tablename__ = "source_chunks"
    __table_args__ = (
        UniqueConstraint("source_id", "position", name="uq_chunks_source_position"),
        CheckConstraint("position >= 0", name="ck_chunks_position"),
        CheckConstraint(
            "start_line >= 1 AND end_line >= start_line", name="ck_chunks_lines"
        ),
        Index("ix_chunks_user_project_source", "user_id", "project_id", "source_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    start_line: Mapped[int] = mapped_column(nullable=False)
    end_line: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    source: Mapped[SourceDocument] = relationship(back_populates="chunks")


class ProcessingTask(TimestampMixin, Base):
    __tablename__ = "processing_tasks"
    __table_args__ = (
        Index("ix_tasks_project_status", "project_id", "status"),
        CheckConstraint(
            "progress >= 0 AND progress <= 100", name="ck_tasks_progress_range"
        ),
        CheckConstraint("attempt_count >= 0", name="ck_tasks_attempt_count"),
        Index("ix_tasks_user_queue", "user_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(
            TaskStatus,
            values_callable=lambda items: [item.value for item in items],
            native_enum=False,
            length=20,
        ),
        default=TaskStatus.QUEUED,
        nullable=False,
    )
    stage: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    progress: Mapped[int] = mapped_column(default=0, nullable=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)

    project: Mapped[Project] = relationship(back_populates="tasks")
    source: Mapped[SourceDocument] = relationship(back_populates="tasks")
    candidates: Mapped[list["CandidateKnowledge"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class CandidateKnowledge(TimestampMixin, Base):
    __tablename__ = "candidate_knowledge"
    __table_args__ = (
        Index("ix_candidates_project_review", "project_id", "review_status"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_candidates_confidence_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_tasks.id", ondelete="CASCADE"), nullable=False
    )
    candidate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(
            ReviewStatus,
            values_callable=lambda items: [item.value for item in items],
            native_enum=False,
            length=20,
        ),
        default=ReviewStatus.PENDING,
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="candidates")
    source: Mapped[SourceDocument] = relationship(back_populates="candidates")
    task: Mapped[ProcessingTask] = relationship(back_populates="candidates")


class ReviewEvent(Base):
    __tablename__ = "review_events"
    __table_args__ = (
        Index("ix_review_events_candidate", "candidate_id", "created_at"),
        CheckConstraint("action IN ('confirm', 'reject')", name="ck_review_events_action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_knowledge.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    before: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    after: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

