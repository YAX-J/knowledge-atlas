import hashlib
import json

from sqlalchemy import select

from app.core.errors import AppError
from app.models.domain import SourceDocument, utc_now
from app.models.library import AnswerFeedback, SourceArchive
from app.models.workspace import ConversationTurn
from app.services.projects import get_project


def archived_source_condition():
    return select(SourceArchive.source_id).where(
        SourceArchive.source_id == SourceDocument.id,
        SourceArchive.user_id == SourceDocument.user_id,
        SourceArchive.project_id == SourceDocument.project_id,
        SourceArchive.archived.is_(True),
    ).correlate(SourceDocument).exists()


def source_archived(db, source):
    return bool(db.scalar(select(SourceArchive.archived).where(
        SourceArchive.source_id == source.id, SourceArchive.user_id == source.user_id,
        SourceArchive.project_id == source.project_id)))


def archive_source(db, *, user_id, project_id, source_id, request):
    get_project(db, user_id=user_id, project_id=project_id, lock=True)
    source = db.scalar(select(SourceDocument).where(SourceDocument.id == source_id,
        SourceDocument.user_id == user_id, SourceDocument.project_id == project_id))
    if source is None:
        raise AppError(status_code=404, code='SOURCE_NOT_FOUND', message='资料不存在')
    state = db.get(SourceArchive, source_id)
    if state is None:
        state = SourceArchive(source_id=source_id, user_id=user_id, project_id=project_id,
            archived=request.archived, reason=request.reason)
        db.add(state)
    elif state.archived != request.archived:
        state.archived, state.reason = request.archived, request.reason
    db.commit()
    return dict(source_id=source_id, archived=state.archived)


def _turn(db, user_id, project_id, turn_id):
    get_project(db, user_id=user_id, project_id=project_id)
    turn = db.scalar(select(ConversationTurn).where(ConversationTurn.id == turn_id,
        ConversationTurn.user_id == user_id, ConversationTurn.project_id == project_id,
        ConversationTurn.status == 'succeeded'))
    if turn is None or not turn.answer:
        raise AppError(status_code=404, code='ANSWER_NOT_FOUND', message='已保存回答不存在')
    return turn


def list_feedback(db, *, user_id, project_id, turn_id):
    _turn(db, user_id, project_id, turn_id)
    return list(db.scalars(select(AnswerFeedback).where(AnswerFeedback.user_id == user_id,
        AnswerFeedback.project_id == project_id, AnswerFeedback.turn_id == turn_id)
        .order_by(AnswerFeedback.created_at.desc(), AnswerFeedback.id).limit(50)))


def create_feedback(db, *, user_id, project_id, turn_id, request):
    get_project(db, user_id=user_id, project_id=project_id, lock=True)
    turn = _turn(db, user_id, project_id, turn_id)
    claims = turn.answer.get('claims') or []
    if request.claim_index >= len(claims):
        raise AppError(status_code=422, code='ANSWER_CLAIM_NOT_FOUND', message='该回答没有所选结论')
    digest = hashlib.sha256(json.dumps(turn.answer, sort_keys=True, ensure_ascii=False,
        separators=(',', ':')).encode()).hexdigest()
    existing = db.get(AnswerFeedback, request.request_id)
    expected = (user_id, project_id, turn_id, digest, request.claim_index, request.category, request.comment)
    if existing:
        actual = (existing.user_id, existing.project_id, existing.turn_id, existing.answer_sha256,
            existing.claim_index, existing.category, existing.comment)
        if actual != expected:
            raise AppError(status_code=409, code='FEEDBACK_REQUEST_CONFLICT', message='提交标识已用于其他反馈')
        db.commit()
        return existing
    item = AnswerFeedback(id=request.request_id, user_id=user_id, project_id=project_id,
        turn_id=turn_id, answer_sha256=digest, claim_index=request.claim_index,
        claim_text=claims[request.claim_index]['text'], category=request.category,
        comment=request.comment, created_at=utc_now())
    db.add(item); db.commit(); db.refresh(item)
    return item
