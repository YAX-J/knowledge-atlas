import uuid
from typing import Literal, get_args

from fastapi import APIRouter, Query
from pydantic import AwareDatetime

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.knowledge import EntityType
from app.schemas.search import EmbeddingJobRead, EmbeddingRebuildRead, EmbeddingStatusRead, SearchRead
from app.services.embeddings import project_embedding_status
from app.services.search import search_knowledge
from app.services import embedding_jobs


router = APIRouter(tags=['search'])


@router.get('/projects/{project_id}/search', response_model=SearchRead)
def search(
    project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
    q: str = Query(min_length=1, max_length=200), mode: Literal['keyword', 'bm25', 'bm25_source', 'vector', 'hybrid', 'rrf'] = 'keyword',
    types: str = Query(default='', max_length=500), valid_at: AwareDatetime | None = None,
    top_k: int = Query(default=10, ge=1, le=50),
):
    selected = [value.strip() for value in types.split(',') if value.strip()]
    if set(selected) - set(get_args(EntityType)):
        raise AppError(status_code=422, code='SEARCH_TYPES_INVALID', message='搜索筛选包含未知知识类型')
    return search_knowledge(db, user_id=user_id, project_id=project_id, query=q,
                            types=selected, valid_at=valid_at, top_k=top_k,
                            mode=mode, settings=get_settings())


@router.post('/projects/{project_id}/embeddings/rebuild', response_model=EmbeddingRebuildRead)
def rebuild_embeddings(project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId, retry_interrupted: bool = False):
    return embedding_jobs.rebuild(
        db, user_id=user_id, project_id=project_id, settings=get_settings(), retry_interrupted=retry_interrupted,
    )


@router.get('/projects/{project_id}/embeddings/rebuild-status', response_model=EmbeddingJobRead | None)
def rebuild_status(project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId):
    return embedding_jobs.read_job(db, user_id=user_id, project_id=project_id)


@router.get('/projects/{project_id}/embeddings/status', response_model=EmbeddingStatusRead)
def embedding_status(project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
                     valid_at: AwareDatetime | None = None):
    return project_embedding_status(db, user_id=user_id, project_id=project_id,
                                    settings=get_settings(), valid_at=valid_at)
