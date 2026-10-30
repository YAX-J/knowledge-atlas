"""Fenced progress commits at read-only agent boundaries; no business auto-flush."""
from datetime import timedelta
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.agents.runtime import RunContext
from app.core.errors import AppError
from app.models.agent_run import AgentRun
from app.models.domain import Project, utc_now


RUN_LEASE_SECONDS = 1200


def save_progress(
    db: Session, *, context: RunContext, execution_id: uuid.UUID, result: dict | None = None,
) -> None:
    # The coordinator calls this only before/after read-only tools/providers or
    # after the extraction service has committed validated candidates. A shared
    # session commit must never flush unfinished business writes as a side effect.
    if db.new or db.dirty or db.deleted:
        raise AppError(status_code=503, code='WORKFLOW_PROGRESS_UNAVAILABLE',
            message='任务存在未完成的数据写入，已停止后续调用，请读取任务状态')
    now = utc_now()
    values = dict(events=[dict(event) for event in context.events], usage=context.usage(),
        lease_until=now + timedelta(seconds=RUN_LEASE_SECONDS))
    if result is not None:
        values['result'] = dict(result)
    try:
        with db.no_autoflush:
            changed = db.execute(update(AgentRun).where(
                AgentRun.id == context.run_id, AgentRun.user_id == context.user_id,
                AgentRun.project_id == context.project_id, AgentRun.status == 'running',
                AgentRun.execution_id == execution_id, AgentRun.lease_until > now,
                AgentRun.project_id.in_(select(Project.id).where(Project.user_id == context.user_id,
                    Project.archived_at.is_(None))),
            ).values(**values).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise AppError(status_code=409, code='WORKFLOW_INTERRUPTED',
                message='任务执行归属已失效，已停止后续调用，请读取已保存状态')
        db.commit()
    except AppError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise AppError(status_code=503, code='WORKFLOW_PROGRESS_UNAVAILABLE',
            message='任务进度暂时无法保存，已停止后续调用，请读取任务状态') from None
