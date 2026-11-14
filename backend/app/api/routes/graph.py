import uuid
from typing import get_args

from fastapi import APIRouter, Query
from pydantic import AwareDatetime

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.graph import EntityDetail, GraphRead, GraphTimelineRead, Neo4jGraphRead, Neo4jGraphSync, RelationshipDetail
from app.schemas.knowledge import EntityType
from app.services import graph, neo4j_graph


router = APIRouter(tags=["graph"])


def _graph_types(types: str) -> list[str]:
    selected = [item.strip() for item in types.split(",") if item.strip()]
    if set(selected) - set(get_args(EntityType)):
        raise AppError(status_code=422, code="GRAPH_TYPES_INVALID", message="图谱筛选包含未知知识类型")
    return selected


@router.get("/projects/{project_id}/graph", response_model=GraphRead)
def get_graph(
    project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
    center_id: uuid.UUID | None = None, depth: int = Query(default=1, ge=1, le=2),
    types: str = Query(default="", max_length=500), valid_at: AwareDatetime | None = None,
    limit: int = Query(default=100, ge=1, le=200),
):
    return graph.get_graph(db, user_id=user_id, project_id=project_id, center_id=center_id,
                           depth=depth, types=_graph_types(types), valid_at=valid_at, limit=limit)


@router.get("/projects/{project_id}/graph/timeline", response_model=GraphTimelineRead)
def get_timeline(project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId):
    return graph.timeline(db, user_id=user_id, project_id=project_id)


@router.get("/health/neo4j")
def neo4j_health():
    neo4j_graph.check_connection(get_settings())
    return {"status": "up"}


@router.post("/projects/{project_id}/graph/neo4j/sync", response_model=Neo4jGraphSync)
def sync_neo4j_graph(
    project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId, valid_at: AwareDatetime | None = None,
):
    return neo4j_graph.sync_project(db, get_settings(), user_id=user_id, project_id=project_id, valid_at=valid_at)


@router.get("/projects/{project_id}/graph/neo4j", response_model=Neo4jGraphRead)
def get_neo4j_graph(
    project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
    center_id: uuid.UUID | None = None, depth: int = Query(default=1, ge=1, le=2),
    types: str = Query(default="", max_length=500), limit: int = Query(default=100, ge=1, le=200),
):
    return neo4j_graph.read_project(db, get_settings(), user_id=user_id, project_id=project_id,
                                   center_id=center_id, depth=depth, types=_graph_types(types), limit=limit)


@router.get("/knowledge/entities/{entity_id}", response_model=EntityDetail)
def entity_detail(entity_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId, valid_at: AwareDatetime | None = None):
    return graph.entity_detail(db, user_id=user_id, entity_id=entity_id, valid_at=valid_at)


@router.get("/knowledge/relationships/{relationship_id}", response_model=RelationshipDetail)
def relationship_detail(relationship_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId, valid_at: AwareDatetime | None = None):
    return graph.relationship_detail(db, user_id=user_id, relationship_id=relationship_id, valid_at=valid_at)
