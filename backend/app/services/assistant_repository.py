"""Deterministic, checkpointed repository preparation for the assistant runner."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, case, func, select

from app.core.errors import AppError
from app.models.domain import ProcessingTask, RepositorySnapshot, RepositorySnapshotFile, SourceDocument, utc_now
from app.services import assistant_operations as ops, github_import
from app.services.lexical import tokenize
from app.services.parsing import PARSING_TASK_TYPES, run_task
from app.services.repositories import get_repository


def _save(db, item, execution, progress, lease_seconds):
    ops.guard(db, item, execution, lock=True)
    item.request = {**item.request, 'scope': {**item.request['scope'], 'repository_progress': progress}}
    item.lease_until = utc_now() + timedelta(seconds=lease_seconds)


def _files(item, snapshot_id):
    file = RepositorySnapshotFile
    source = SourceDocument
    task = ProcessingTask
    return (
        select(file.path, source.id.label('source_id'), source.size_bytes, task.id.label('task_id'), task.status)
        .select_from(file)
        .join(RepositorySnapshot, and_(RepositorySnapshot.id == file.snapshot_id,
              RepositorySnapshot.user_id == item.user_id, RepositorySnapshot.project_id == item.project_id,
              RepositorySnapshot.repository_id == UUID(item.request['repository_id'])))
        .join(source, and_(source.id == file.source_id, source.project_id == item.project_id,
                           source.user_id == item.user_id, source.repository_id == UUID(item.request['repository_id'])))
        .join(task, and_(task.id == file.task_id, task.source_id == source.id, task.user_id == item.user_id,
                         task.project_id == item.project_id, task.type.in_(PARSING_TASK_TYPES)))
        .where(file.snapshot_id == snapshot_id, file.status.notin_(('deleted', 'skipped')))
    )


def prepare(db, item, execution, request, settings, lease_seconds):
    scope = item.request['scope']
    progress = scope['repository_progress']
    repo = get_repository(db, user_id=item.user_id, project_id=item.project_id, repository_id=request.repository_id)
    if [repo.provider, repo.remote_owner, repo.remote_name] != scope['repository_identity']:
        raise AppError(status_code=409, code='ASSISTANT_REPOSITORY_CHANGED', message='仓库身份已变化')
    pinned_provider_id = progress.get('provider_repository_id') or scope.get('repository_provider_id')
    if pinned_provider_id and repo.provider_repository_id != pinned_provider_id:
        raise AppError(status_code=409, code='ASSISTANT_REPOSITORY_CHANGED', message='仓库身份已变化')

    def guard():
        ops.guard(db, item, execution)

    def save_batch(result):
        nonlocal progress
        if [repo.provider, repo.remote_owner, repo.remote_name] != scope['repository_identity']:
            raise AppError(status_code=409, code='ASSISTANT_REPOSITORY_CHANGED', message='仓库身份已变化')
        if not result.truncated and not result.deletion_detection_complete:
            raise AppError(status_code=409, code='ASSISTANT_REPOSITORY_INCOMPLETE', message='仓库快照不完整')
        progress = {**progress, 'phase': 'importing' if result.truncated else 'parsing',
                    'snapshot_id': str(result.snapshot_id), 'commit_sha': result.commit_sha, 'ref': result.ref,
                    'completed_files': result.completed_files or 0, 'total_files': result.total_supported_files or 0,
                    'pending_directories': result.pending_directories, 'blocked': result.traversal_blocked,
                    'provider_repository_id': repo.provider_repository_id}
        _save(db, item, execution, progress, lease_seconds)

    if progress['phase'] == 'importing':
        if progress.get('blocked'):
            raise AppError(status_code=409, code='GITHUB_TRAVERSAL_BLOCKED', message='文件树达到 GitHub 遍历上限')
        previous = progress
        snapshot = UUID(progress['snapshot_id']) if progress['snapshot_id'] else None
        result = github_import.sync_github_repository(
            db, settings=settings, user_id=item.user_id, project_id=item.project_id,
            repository_id=request.repository_id,
            requested_ref=progress.get('ref') or request.repository_commit or request.repository_ref,
            expected_commit_sha=progress.get('commit_sha') or request.repository_commit,
            continue_from_snapshot=snapshot, resume_incomplete=True, request_guard=guard, save_progress=save_batch,
        )
        if result.truncated and (not result.continuation_snapshot_id or (
            result.tree_complete and previous['snapshot_id'] and
            previous['completed_files'] >= progress['completed_files']
        )):
            raise AppError(status_code=409, code='ASSISTANT_REPOSITORY_INCOMPLETE', message='仓库导入未能继续')
        if progress['phase'] == 'importing':
            return None

    snapshot_id = UUID(progress['snapshot_id'])
    if progress['phase'] == 'parsing':
        files = _files(item, snapshot_id).subquery()
        priority = case((files.c.status == 'queued', 0), else_=1).label('priority')
        pending = [row.task_id for row in db.execute(select(files.c.task_id, priority)
                   .where(files.c.status.in_(('queued', 'running'))).distinct().order_by(priority, files.c.task_id).limit(50))]
        for task_id in pending:
            guard()
            try:
                with ops.fenced(db, item, execution):
                    run_task(db, user_id=item.user_id, task_id=task_id, settings=settings,
                             recover_expired=True, retry_failed=False)
            except AppError as error:
                if error.code != 'TASK_NOT_RUNNABLE':
                    raise
        counts = dict(db.execute(select(files.c.status, func.count()).group_by(files.c.status)).all())
        waiting = counts.get('queued', 0) + counts.get('running', 0)
        progress = {**progress, 'parsed_files': counts.get('succeeded', 0), 'waiting_files': waiting,
                    'failed_files': counts.get('failed', 0) + counts.get('cancelled', 0),
                    'skipped_files': max(0, progress['total_files'] - sum(counts.values())),
                    'phase': 'parsing' if waiting else 'reporting'}
        _save(db, item, execution, progress, lease_seconds)
        db.commit()
        if waiting:
            return None

    if 'report_sources' in progress:
        return snapshot_id, progress['commit_sha'], {UUID(key): path for key, path in progress['report_sources']}

    files = _files(item, snapshot_id).subquery()
    terms = set(tokenize(request.goal))
    matches = [case((func.lower(files.c.path).contains(term, autoescape=True), 1), else_=0)
               for term in sorted(terms, key=lambda term: (-len(term), term))[:12]]
    score = sum(matches) if matches else files.c.size_bytes * 0
    rows = db.execute(select(files.c.path, files.c.source_id, files.c.size_bytes)
                      .where(files.c.status == 'succeeded')
                      .order_by(score.desc(), case((func.lower(files.c.path).like('%readme%'), 0), else_=1),
                                files.c.path, files.c.source_id).limit(200))
    paths = {}
    size = 0
    for row in rows:
        if row.source_id not in paths and size + row.size_bytes <= 200000:
            paths[row.source_id] = row.path
            size += row.size_bytes
            if len(paths) == 20:
                break
    progress = {**progress, 'report_sources': [(str(key), path) for key, path in paths.items()]}
    _save(db, item, execution, progress, lease_seconds)
    db.commit()
    return snapshot_id, progress['commit_sha'], paths
