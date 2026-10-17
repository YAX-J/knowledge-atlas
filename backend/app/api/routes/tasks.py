import uuid

from fastapi import APIRouter

from app.api.dependencies import CurrentUserId, DatabaseSession
from app.schemas.tasks import TaskRead
from app.services import ingestion


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: uuid.UUID,
    db: DatabaseSession,
    user_id: CurrentUserId,
) -> TaskRead:
    return ingestion.get_task(db, user_id=user_id, task_id=task_id)

