"""Optional database-backed source parser: python -m app.worker [--once]."""

import argparse
import logging
import signal
import threading
import uuid
from collections.abc import Callable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.identity import DEVELOPMENT_USER_ID
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.models.domain import ProcessingTask, Project, SourceDocument, TaskStatus, utc_now
from app.services.parsing import PARSING_TASK_TYPES, expired_task_filter, run_task
from app.services.source_languages import TASK_TYPES_BY_SOURCE


logger = logging.getLogger(__name__)


def process_next(
    db: Session, *, user_id: uuid.UUID, settings: Settings,
) -> ProcessingTask | None:
    candidates = list(db.scalars(
        select(ProcessingTask)
        .join(SourceDocument, SourceDocument.id == ProcessingTask.source_id)
        .join(Project, Project.id == ProcessingTask.project_id)
        .where(
            ProcessingTask.user_id == user_id,
            SourceDocument.user_id == user_id,
            SourceDocument.project_id == ProcessingTask.project_id,
            SourceDocument.source_type.in_(tuple(TASK_TYPES_BY_SOURCE)),
            Project.user_id == user_id,
            Project.archived_at.is_(None),
            ProcessingTask.type.in_(PARSING_TASK_TYPES),
            or_(
                ProcessingTask.status == TaskStatus.QUEUED,
                expired_task_filter(utc_now(), settings.task_lease_seconds),
            ),
        )
        .order_by(ProcessingTask.created_at, ProcessingTask.id)
        .limit(10)
        .execution_options(populate_existing=True)
    ))
    for candidate in candidates:
        try:
            result = run_task(
                db, user_id=user_id, task_id=candidate.id, settings=settings,
                recover_expired=True, retry_failed=False,
            )
        except AppError as error:
            if error.code in {"TASK_NOT_RUNNABLE", "TASK_NOT_FOUND", "SOURCE_NOT_FOUND", "PROJECT_NOT_FOUND"}:
                db.rollback()
                continue
            raise
        logger.info("task_processed task_id=%s status=%s", result.id, result.status.value)
        return result
    db.rollback()
    return None


def serve(
    *, settings: Settings, user_id: uuid.UUID, once: bool,
    stop: threading.Event, session_factory: Callable[[], Session] = SessionLocal,
) -> int:
    while not stop.is_set():
        try:
            with session_factory() as db:
                task = process_next(db, user_id=user_id, settings=settings)
        except Exception as error:
            # SQL exceptions can contain source text and connection credentials.
            logger.error("worker_iteration_failed error_type=%s", type(error).__name__)
            if once:
                return 1
            stop.wait(settings.worker_poll_interval_seconds)
            continue
        if once:
            return 1 if task is not None and task.status == TaskStatus.FAILED else 0
        if task is None:
            stop.wait(settings.worker_poll_interval_seconds)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Consume queued source parsing tasks")
    parser.add_argument("--once", action="store_true", help="Handle at most one task and exit")
    parser.add_argument("--user-id", type=uuid.UUID, default=DEVELOPMENT_USER_ID,
                        help="Only process this user's projects (development user by default)")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.app_env)
    stop = threading.Event()

    def request_stop(signum: int, frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    logger.info("worker_started user_id=%s once=%s", args.user_id, args.once)
    return serve(settings=settings, user_id=args.user_id, once=args.once, stop=stop)


if __name__ == "__main__":
    raise SystemExit(main())
