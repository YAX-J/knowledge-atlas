"""Bounded read-only multi-language symbol search over ready project sources."""

import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.models.domain import ProcessingTask, SourceChunk, SourceDocument, SourceStatus
from app.schemas.sources import CodeSymbolHit, CodeSymbolSearchResult
from app.services.ingestion import PARSING_TASK_TYPES
from app.services.java_source import java_symbols
from app.services.code_source import analyze_code
from app.services.source_languages import CODE_SOURCE_TYPES
from app.services.projects import get_project
from app.services.repositories import get_repository
from app.services.source_links import github_file_urls, github_line_url


MAX_SEARCH_SOURCES = 100
MAX_SEARCH_BYTES = 20 * 1024 * 1024


def search_symbols(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID,
    query: str, repository_id: uuid.UUID | None, kind: str | None, limit: int,
) -> CodeSymbolSearchResult:
    get_project(db, user_id=user_id, project_id=project_id)
    if repository_id is not None:
        get_repository(db, user_id=user_id, project_id=project_id, repository_id=repository_id)
    query = query.strip()
    if not query:
        raise AppError(status_code=422, code="CODE_SEARCH_QUERY_EMPTY", message="请输入符号名称或文件路径")

    filters = [
        SourceDocument.user_id == user_id,
        SourceDocument.project_id == project_id,
        SourceDocument.source_type.in_(tuple(CODE_SOURCE_TYPES)),
        SourceDocument.status == SourceStatus.READY,
    ]
    if repository_id is not None:
        filters.append(SourceDocument.repository_id == repository_id)
    # Bound metadata before loading immutable source text. Keep old versions as
    # separate results and make omissions visible rather than claiming no match.
    metadata = list(db.execute(
        select(SourceDocument.id, SourceDocument.size_bytes).where(*filters)
        .order_by(SourceDocument.created_at, SourceDocument.id)
        .limit(MAX_SEARCH_SOURCES + 1)
    ))
    truncated = len(metadata) > MAX_SEARCH_SOURCES
    source_ids: list[uuid.UUID] = []
    byte_count = 0
    for source_id, size in metadata[:MAX_SEARCH_SOURCES]:
        if byte_count + size > MAX_SEARCH_BYTES:
            truncated = True
            continue
        source_ids.append(source_id)
        byte_count += size

    sources = list(db.scalars(
        select(SourceDocument).where(*filters, SourceDocument.id.in_(source_ids))
        .options(selectinload(SourceDocument.repository))
        .order_by(SourceDocument.created_at, SourceDocument.id)
    )) if source_ids else []
    needle = query.casefold()
    hits: list[CodeSymbolHit] = []
    has_syntax_errors = False
    for source in sources:
        if source.source_type == "java":
            symbols, omitted = java_symbols(source.content, source_id=source.id)
        else:
            analysis = analyze_code(source.content, source_id=source.id, language=source.source_type)
            symbols, omitted = analysis.symbols, analysis.truncated
            has_syntax_errors |= analysis.has_syntax_errors
        truncated |= omitted
        path = source.relative_path or source.original_name
        for symbol in symbols:
            if kind is not None and symbol.kind != kind:
                continue
            if needle not in symbol.qualified_name.casefold() and needle not in path.casefold():
                continue
            hits.append(CodeSymbolHit(
                **vars(symbol), language=source.source_type, source_id=source.id, source_path=path,
                repository_id=source.repository_id,
                repository_name=source.repository.name if source.repository else None,
                task_id=None,
            ))
    # Prefer exact names, then qualified names, then path-only matches. UUIDs
    # break ties reproducibly without collapsing immutable source versions.
    hits.sort(key=lambda hit: (
        0 if hit.name.casefold() == needle else
        1 if needle in hit.qualified_name.casefold() else 2,
        hit.source_path.casefold(), hit.start_line, hit.kind, str(hit.id),
    ))
    matched_count = len(hits)
    truncated |= matched_count > limit
    hits = hits[:limit]
    selected_ids = {hit.source_id for hit in hits}
    if hits:
        tasks: dict[uuid.UUID, uuid.UUID] = {}
        for task in db.scalars(select(ProcessingTask).where(
            ProcessingTask.user_id == user_id, ProcessingTask.project_id == project_id,
            ProcessingTask.source_id.in_(selected_ids), ProcessingTask.type.in_(PARSING_TASK_TYPES),
        ).order_by(ProcessingTask.created_at.desc(), ProcessingTask.id.desc())):
            tasks.setdefault(task.source_id, task.id)
        urls = github_file_urls(db, user_id=user_id, project_id=project_id, source_ids=list(selected_ids))
        chunks = list(db.scalars(select(SourceChunk).where(
            SourceChunk.user_id == user_id, SourceChunk.project_id == project_id,
            or_(*(and_(SourceChunk.source_id == hit.source_id,
                       SourceChunk.start_line <= hit.start_line,
                       SourceChunk.end_line >= hit.start_line) for hit in hits)),
        ).order_by(SourceChunk.position)))
        for hit in hits:
            hit.task_id = tasks.get(hit.source_id)
            hit.git_url = github_line_url(urls.get(hit.source_id), start_line=hit.start_line, end_line=hit.end_line)
            chunk = next((item for item in chunks if item.source_id == hit.source_id
                          and item.start_line <= hit.start_line <= item.end_line), None)
            if chunk is not None:
                hit.chunk_id = chunk.id
                hit.chunk_position = chunk.position
    return CodeSymbolSearchResult(
        query=query, items=hits, scanned_source_count=len(sources),
        matched_count=matched_count, truncated=truncated, has_syntax_errors=has_syntax_errors,
    )
