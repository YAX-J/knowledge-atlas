import uuid
from fastapi import APIRouter, Query
from app.api.dependencies import CurrentUserId, DatabaseSession
from app.core.config import get_settings
from app.schemas.conversations import ConversationCreate, ConversationList, ConversationRead, TurnCreate, TurnList, TurnRead
from app.services import conversations

router = APIRouter(tags=['conversations'])


@router.post('/projects/{project_id}/conversations', response_model=ConversationRead, status_code=201)
def create(project_id: uuid.UUID, request: ConversationCreate, db: DatabaseSession, user_id: CurrentUserId):
    return conversations.create(db, user_id=user_id, project_id=project_id, title=request.title)


@router.get('/projects/{project_id}/conversations', response_model=ConversationList)
def listing(project_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
            page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return conversations.listing(db, user_id=user_id, project_id=project_id, page=page, page_size=page_size)


@router.get('/projects/{project_id}/conversations/{conversation_id}/turns', response_model=TurnList)
def turns(project_id: uuid.UUID, conversation_id: uuid.UUID, db: DatabaseSession, user_id: CurrentUserId,
          page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return conversations.turns(db, user_id=user_id, project_id=project_id, conversation_id=conversation_id, page=page, page_size=page_size)


@router.post('/projects/{project_id}/conversations/{conversation_id}/turns', response_model=TurnRead)
def answer(project_id: uuid.UUID, conversation_id: uuid.UUID, request: TurnCreate, db: DatabaseSession, user_id: CurrentUserId):
    return conversations.answer(db, user_id=user_id, project_id=project_id, conversation_id=conversation_id, request=request, settings=get_settings())
