import uuid
from typing import get_args

from fastapi import APIRouter, Query
from pydantic import AwareDatetime

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.core.errors import AppError
from app.schemas.graph import EntityDetail, GraphRead, RelationshipDetail
from app.schemas.knowledge import EntityType
from app.services import graph


router = APIRouter(tags=["graph"])


@router.get("/projects/{project_id}/graph", response_model=GraphRead)
def get_graph(
    project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
    center_id: uuid.UUID | None = None, depth: int = Query(default=1, ge=1, le=2),
    types: str = Query(default="", max_length=500), valid_at: AwareDatetime | None = None,
    limit: int = Query(default=100, ge=1, le=200),
):
    selected_types = [item.strip() for item in types.split(",") if item.strip()]
    if set(selected_types) - set(get_args(EntityType)):
        raise AppError(status_code=422, code="GRAPH_TYPES_INVALID", message="图谱筛选包含未知知识类型")
    return graph.get_graph(db, user_id=user_id, project_id=project_id, center_id=center_id,
                           depth=depth, types=selected_types, valid_at=valid_at, limit=limit)


@router.get("/knowledge/entities/{entity_id}", response_model=EntityDetail)
def entity_detail(entity_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId, valid_at: AwareDatetime | None = None):
    return graph.entity_detail(db, user_id=user_id, entity_id=entity_id, valid_at=valid_at)


@router.get("/knowledge/relationships/{relationship_id}", response_model=RelationshipDetail)
def relationship_detail(relationship_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId, valid_at: AwareDatetime | None = None):
    return graph.relationship_detail(db, user_id=user_id, relationship_id=relationship_id, valid_at=valid_at)
