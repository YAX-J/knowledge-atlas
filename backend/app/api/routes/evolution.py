import uuid
from typing import Literal

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.schemas.evolution import ChangeCreate, ChangeList, ChangeRead, ChangeResolve, EvolutionRead, GovernanceKind, GovernanceRead
from app.services import evolution

router = APIRouter(tags=["evolution"])


@router.post("/projects/{project_id}/knowledge-changes", response_model=ChangeRead)
def propose(project_id: uuid.UUID, proposal: ChangeCreate, db: DatabaseSession, user_id: CurrentUserId):
    return evolution.create_change(db, user_id=user_id, project_id=project_id, proposal=proposal)


@router.get("/projects/{project_id}/knowledge-changes", response_model=ChangeList)
def listing(project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
            review_status: Literal["pending", "confirmed", "rejected"] | None = None,
            page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
    return evolution.list_changes(db, user_id=user_id, project_id=project_id, review_status=review_status,
                                  page=page, page_size=page_size)


@router.post("/projects/{project_id}/knowledge-changes/{change_id}/resolve", response_model=ChangeRead)
def resolve(project_id: uuid.UUID, change_id: uuid.UUID, decision: ChangeResolve,
            db: DatabaseSession, user_id: CurrentUserId):
    return evolution.resolve_change(db, user_id=user_id, project_id=project_id, change_id=change_id, action=decision.action)


@router.get("/projects/{project_id}/knowledge/entities/{entity_id}/history", response_model=EvolutionRead)
def history(project_id: uuid.UUID, entity_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId):
    return evolution.history(db, user_id=user_id, project_id=project_id, entity_id=entity_id)


@router.get("/projects/{project_id}/governance", response_model=GovernanceRead)
def governance(project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
               limit: int = Query(default=200, ge=1, le=500), kind: GovernanceKind | None = None):
    return evolution.governance(db, user_id=user_id, project_id=project_id, limit=limit, kind=kind)
