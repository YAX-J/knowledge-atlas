import uuid

from fastapi import APIRouter

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.core.config import get_settings
from app.schemas.questions import QuestionCreate, QuestionRead
from app.services.questions import answer_question


router = APIRouter(tags=['questions'])


@router.post('/projects/{project_id}/questions', response_model=QuestionRead)
def ask_question(
    project_id: uuid.UUID, request: QuestionCreate,
    db: DatabaseSession, user_id: CurrentUserId,
):
    return answer_question(
        db, user_id=user_id, project_id=project_id, question=request.question,
        valid_at=request.valid_at, settings=get_settings(), retrieval_mode=request.retrieval_mode,
    )
