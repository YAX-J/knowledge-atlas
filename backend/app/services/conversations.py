"""Bounded conversational context is a hint; only fresh scoped evidence can support an answer."""
import uuid
from datetime import timedelta
from sqlalchemy import func, select
from app.core.errors import AppError
from app.models.domain import utc_now
from app.models.graph import KnowledgeEntity
from app.models.workspace import Conversation, ConversationTurn
from app.schemas.conversations import ConversationList, ConversationRead, TurnList, TurnRead
from app.services import graph, questions
from app.services.evolution import aware
from app.services.projects import get_project
from app.services.question_time import resolve_question_time


def _conversation(db, user_id, project_id, conversation_id, *, lock=False):
    get_project(db, user_id=user_id, project_id=project_id)
    query = select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id,
        Conversation.project_id == project_id, Conversation.archived.is_(False)).execution_options(populate_existing=True)
    item = db.scalar(query.with_for_update() if lock else query)
    if item is None:
        raise AppError(status_code=404, code='CONVERSATION_NOT_FOUND', message='会话不存在或不属于此项目')
    return item


def create(db, *, user_id, project_id, title):
    get_project(db, user_id=user_id, project_id=project_id)
    record = Conversation(user_id=user_id, project_id=project_id, title=title)
    db.add(record)
    db.commit()
    return ConversationRead.model_validate(record)


def listing(db, *, user_id, project_id, page, page_size):
    get_project(db, user_id=user_id, project_id=project_id)
    query = select(Conversation).where(Conversation.user_id == user_id, Conversation.project_id == project_id,
        Conversation.archived.is_(False))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    records = db.scalars(query.order_by(Conversation.updated_at.desc(), Conversation.id).offset((page-1)*page_size).limit(page_size))
    return ConversationList(items=[ConversationRead.model_validate(item) for item in records], total=total, page=page, page_size=page_size)


def turns(db, *, user_id, project_id, conversation_id, page, page_size):
    _conversation(db, user_id, project_id, conversation_id)
    query = select(ConversationTurn).where(ConversationTurn.conversation_id == conversation_id,
        ConversationTurn.user_id == user_id, ConversationTurn.project_id == project_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    records = list(db.scalars(query.order_by(ConversationTurn.position).offset((page-1)*page_size).limit(page_size)))
    now = utc_now()
    conversation = db.get(Conversation, conversation_id)
    result = []
    for item in records:
        read = TurnRead.model_validate(item)
        if item.status == 'running' and (conversation.active_request_id != item.request_id or
                conversation.lease_until is None or aware(conversation.lease_until) <= now):
            read.status = 'interrupted'
        result.append(read)
    return TurnList(items=result, total=total, page=page, page_size=page_size)


def answer(db, *, user_id, project_id, conversation_id, request, settings):
    conversation = _conversation(db, user_id, project_id, conversation_id, lock=True)
    now = utc_now()
    turn = db.scalar(select(ConversationTurn).where(ConversationTurn.conversation_id == conversation_id,
        ConversationTurn.request_id == request.request_id))
    if turn:
        if (turn.question, turn.retrieval_mode, aware(turn.valid_at) if turn.valid_at else None) != (
                request.question, request.retrieval_mode, request.valid_at):
            raise AppError(status_code=409, code='TURN_REQUEST_CONFLICT', message='此提交标识已用于不同问题')
        if turn.status == 'succeeded':
            db.commit()
            return TurnRead.model_validate(turn)
    live = conversation.active_request_id is not None and conversation.lease_until and aware(conversation.lease_until) > now
    if live:
        raise AppError(status_code=409, code='CONVERSATION_BUSY', message='此会话仍在回答，请读取历史状态')
    if turn and not request.retry_interrupted:
        raise AppError(status_code=409, code='TURN_RETRY_REQUIRED', message='上次结果未知或失败，请明确确认后重试，可能再次计费')
    if conversation.active_request_id:
        abandoned = db.scalar(select(ConversationTurn).where(ConversationTurn.conversation_id == conversation_id,
            ConversationTurn.request_id == conversation.active_request_id, ConversationTurn.status == 'running'))
        if abandoned:
            abandoned.status = 'interrupted'
    if turn is None:
        position = (db.scalar(select(func.max(ConversationTurn.position)).where(ConversationTurn.conversation_id == conversation_id)) or 0) + 1
        if position > 200:
            raise AppError(status_code=409, code='CONVERSATION_LIMIT', message='此会话已达 200 轮，请新建会话')
        turn = ConversationTurn(user_id=user_id, project_id=project_id, conversation_id=conversation_id,
            request_id=request.request_id, position=position, question=request.question,
            retrieval_mode=request.retrieval_mode, valid_at=request.valid_at, created_at=now)
        db.add(turn)
    turn.status, turn.error_code = 'running', None
    time_scope = resolve_question_time(request.question, request.valid_at,
                                      aware(turn.created_at) if turn.created_at else now)
    execution_id = uuid.uuid4()
    conversation.active_request_id = request.request_id
    conversation.active_execution_id = execution_id
    conversation.lease_until = now + timedelta(seconds=settings.deepseek_timeout_seconds + settings.embedding_timeout_seconds + 240)
    conversation.updated_at = now
    previous = list(db.scalars(select(ConversationTurn).where(ConversationTurn.conversation_id == conversation_id,
        ConversationTurn.status == 'succeeded').order_by(ConversationTurn.position.desc()).limit(6)))
    context = [{'question': item.question, 'answer': (item.answer or {}).get('answer', '')[:1000]} for item in reversed(previous)]
    ids = [uuid.UUID(value) for item in previous[:2] for value in (item.answer or {}).get('entity_ids', [])]
    names = list(db.scalars(select(KnowledgeEntity.name).where(KnowledgeEntity.id.in_(ids),
        *graph.visible(KnowledgeEntity, user_id, project_id, time_scope.valid_at)).order_by(KnowledgeEntity.id).limit(5))) if ids and time_scope.valid_at else []
    # Explicit current wording remains first; old context never contributes citations.
    retrieval_query = ' '.join([request.question, *names])[:200] if context and names else request.question
    db.commit()
    try:
        response = questions.answer_question(db, user_id=user_id, project_id=project_id, question=request.question,
            valid_at=request.valid_at, settings=settings, retrieval_mode=request.retrieval_mode,
            context=context, retrieval_query=retrieval_query, time_scope=time_scope)
    except Exception as exc:
        db.rollback()
        current = _conversation(db, user_id, project_id, conversation_id, lock=True)
        if current.active_request_id == request.request_id and current.active_execution_id == execution_id:
            turn = db.get(ConversationTurn, turn.id, populate_existing=True)
            turn.status, turn.error_code = 'failed', exc.code if isinstance(exc, AppError) else 'QUESTION_FAILED'
            current.active_request_id, current.lease_until = None, None
            current.active_execution_id = None
            db.commit()
        raise
    current = _conversation(db, user_id, project_id, conversation_id, lock=True)
    if current.active_request_id != request.request_id or current.active_execution_id != execution_id:
        db.rollback()
        raise AppError(status_code=409, code='TURN_REPLACED', message='此轮回答已被接手，请读取会话历史')
    turn = db.get(ConversationTurn, turn.id, populate_existing=True)
    turn.answer, turn.status = response.model_dump(mode='json'), 'succeeded'
    current.active_request_id, current.lease_until, current.updated_at = None, None, utc_now()
    current.active_execution_id = None
    if turn.position == 1 and current.title == '新的证据会话':
        current.title = request.question[:120]
    db.commit()
    return TurnRead.model_validate(turn)
