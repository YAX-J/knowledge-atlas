import uuid
from typing import Literal

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.core.config import get_settings
from app.models.domain import ReviewStatus
from app.schemas.knowledge import ExtractionPlan, ExtractionRead, ReviewBatchRead, ReviewBatchResolve, ReviewList, ReviewRead, ReviewResolve
from app.services import knowledge


router = APIRouter(tags=["knowledge"])


@router.get("/sources/{source_id}/extraction", response_model=ExtractionRead)
def get_extraction(source_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId):
    return knowledge.get_extraction(db, user_id=user_id, source_id=source_id)


@router.post("/sources/{source_id}/extract", response_model=ExtractionRead)
def extract(source_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
            strategy: Literal['single_step','batched']='single_step',
            plan_sha256: str | None = Query(default=None,pattern='^[0-9a-f]{64}$')):
    return knowledge.run_extraction(db, user_id=user_id, source_id=source_id, settings=get_settings(),
        strategy=strategy,approved_plan_sha256=plan_sha256)


@router.get('/sources/{source_id}/extraction-plan',response_model=ExtractionPlan)
def extraction_plan(source_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId):
    return knowledge.extraction_plan(db,user_id=user_id,source_id=source_id,settings=get_settings())


@router.get("/projects/{project_id}/reviews", response_model=ReviewList)
def list_reviews(
    project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
    source_id: uuid.UUID | None = None, review_status: ReviewStatus | None = None,
    candidate_type: str | None = Query(default=None, max_length=50),
    min_confidence: float | None = Query(default=None, ge=0, le=1),
    kind: Literal['entity', 'relation'] | None = None,
    q: str = Query(default='', max_length=200),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
):
    items, total = knowledge.list_reviews(
        db, user_id=user_id, project_id=project_id, source_id=source_id,
        review_status=review_status, candidate_type=candidate_type, min_confidence=min_confidence,
        page=page, page_size=page_size,
        kind=kind, text_query=q,
    )
    return ReviewList(items=items, total=total, page=page, page_size=page_size)


@router.post("/reviews/{review_id}/resolve", response_model=ReviewRead)
def resolve(review_id: uuid.UUID, decision: ReviewResolve, db: DatabaseSession, user_id: CurrentUserId):
    return knowledge.resolve_review(db, user_id=user_id, review_id=review_id, decision=decision)


@router.post('/projects/{project_id}/reviews/resolve-batch', response_model=ReviewBatchRead)
def resolve_batch(project_id: uuid.UUID, decision: ReviewBatchResolve, db: DatabaseSession, user_id: CurrentUserId):
    return knowledge.resolve_reviews_batch(db, user_id=user_id, project_id=project_id, decision=decision)
