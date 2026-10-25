"""Persisted ownership around explicit synchronous rebuilds; never auto-retry providers."""
import uuid
from datetime import timedelta, timezone

from sqlalchemy import select, update

from app.core.errors import AppError
from app.models.domain import Project, utc_now
from app.models.embedding_job import EmbeddingJob
from app.services.embeddings import rebuild_project_embeddings
from app.services.projects import get_project

LEASE_SECONDS = 900


def interrupted(job):
    expiry = job.lease_expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return job.status == 'running' and expiry <= utc_now()


def read_job(db, *, user_id, project_id):
    get_project(db, user_id=user_id, project_id=project_id)
    job = db.scalar(select(EmbeddingJob).where(EmbeddingJob.project_id == project_id, EmbeddingJob.user_id == user_id)
                    .execution_options(populate_existing=True))
    if job is None:
        return None
    return dict(id=job.execution_id, project_id=job.project_id, status=job.status, interrupted=interrupted(job),
                started_at=job.started_at, lease_expires_at=job.lease_expires_at, completed_at=job.completed_at,
                result=job.result, error=job.error)


def rebuild(db, *, user_id, project_id, settings, retry_interrupted=False):
    get_project(db, user_id=user_id, project_id=project_id)
    db.execute(select(Project.id).where(Project.id == project_id, Project.user_id == user_id).with_for_update())
    job = db.get(EmbeddingJob, project_id, populate_existing=True)
    if job and job.status == 'running' and (not interrupted(job) or not retry_interrupted):
        expired = interrupted(job)
        db.rollback()
        raise AppError(status_code=409, code='EMBEDDING_REBUILD_INTERRUPTED' if expired else 'EMBEDDING_REBUILD_RUNNING',
                       message='索引更新结果尚未确认，请刷新更新状态；中断后需明确重新更新')
    now, execution_id = utc_now(), uuid.uuid4()
    if job is None:
        job = EmbeddingJob(project_id=project_id, user_id=user_id)
        db.add(job)
    job.execution_id, job.status = execution_id, 'running'
    job.started_at, job.lease_expires_at = now, now + timedelta(seconds=LEASE_SECONDS)
    job.completed_at = job.result = job.error = None
    db.commit()

    def checkpoint(commit):
        db.execute(select(Project.id).where(Project.id == project_id, Project.user_id == user_id).with_for_update())
        result = db.execute(update(EmbeddingJob).where(EmbeddingJob.project_id == project_id,
            EmbeddingJob.user_id == user_id, EmbeddingJob.execution_id == execution_id,
            EmbeddingJob.status == 'running').values(lease_expires_at=utc_now() + timedelta(seconds=LEASE_SECONDS))
            .execution_options(synchronize_session=False))
        if result.rowcount != 1:
            db.rollback()
            raise AppError(status_code=409, code='EMBEDDING_REBUILD_REPLACED', message='更新已被接手，请刷新状态')
        if commit:
            db.commit()

    try:
        result = rebuild_project_embeddings(db, user_id=user_id, project_id=project_id, settings=settings, checkpoint=checkpoint)
        db.execute(update(EmbeddingJob).where(EmbeddingJob.project_id == project_id,
            EmbeddingJob.execution_id == execution_id).values(status='succeeded', result=result, completed_at=utc_now())
            .execution_options(synchronize_session=False))
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        error = {'code': exc.code, 'message': exc.message} if isinstance(exc, AppError) else {
            'code': 'EMBEDDING_REBUILD_FAILED', 'message': '索引更新未完成，请刷新状态后重试'}
        db.execute(update(EmbeddingJob).where(EmbeddingJob.project_id == project_id,
            EmbeddingJob.execution_id == execution_id).values(status='failed', error=error, completed_at=utc_now())
            .execution_options(synchronize_session=False))
        db.commit()
        raise
