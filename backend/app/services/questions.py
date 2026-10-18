import uuid

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.questions import QuestionEvidenceRead, QuestionRead, RetrievalSummary
from app.services import deepseek
from app.services.search import search_knowledge


MAX_ANSWER_ENTITIES = 5
MAX_ANSWER_EVIDENCE = 12


def _retrieval_summary(result) -> RetrievalSummary:
    return RetrievalSummary(
        keyword_hits=sum((item.keyword_score or 0) > 0 for item in result.items),
        vector_hits=sum((item.vector_component or 0) > 0 for item in result.items),
        graph_hits=sum((item.graph_score or 0) > 0 for item in result.items),
        indexed_count=result.indexed_count or 0,
        eligible_count=result.eligible_count or 0,
    )


def answer_question(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, question: str,
    valid_at, settings: Settings,
) -> QuestionRead:
    result = search_knowledge(
        db, user_id=user_id, project_id=project_id, query=question, types=[],
        valid_at=valid_at, top_k=MAX_ANSWER_ENTITIES, mode='hybrid', settings=settings,
    )
    retrieval = _retrieval_summary(result)
    evidence_by_id: dict[uuid.UUID, QuestionEvidenceRead] = {}
    for hit in result.items:
        for item in hit.evidence:
            evidence_by_id.setdefault(item.id, QuestionEvidenceRead(
                **item.model_dump(), entity_id=hit.entity.id, entity_name=hit.entity.name,
            ))
            if len(evidence_by_id) >= MAX_ANSWER_EVIDENCE:
                break
        if len(evidence_by_id) >= MAX_ANSWER_EVIDENCE:
            break

    if not evidence_by_id:
        return QuestionRead(
            id=uuid.uuid4(), question=question, supported=False,
            answer='现有已确认知识中没有足够的原文证据回答这个问题。', confidence=0,
            entity_ids=[], evidence=[], retrieval=retrieval,
            missing_information=['请补充并确认包含答案的项目资料。'],
        )
    if settings.deepseek_api_key is None:
        raise AppError(
            status_code=503, code='QUESTION_NOT_CONFIGURED',
            message='证据问答尚未配置 DeepSeek API 密钥',
        )

    evidence_payload = [{
        'id': str(item.id), 'entity_name': item.entity_name, 'title': item.title,
        'start_line': item.start_line, 'end_line': item.end_line, 'quote': item.quote,
    } for item in evidence_by_id.values()]
    try:
        draft = deepseek.answer_question(settings, question, evidence_payload)
    except deepseek.QuestionError as exc:
        raise AppError(status_code=503, code=exc.code, message=exc.message) from exc

    unknown = set(draft.citation_ids) - set(evidence_by_id)
    if unknown:
        raise AppError(
            status_code=502, code='QUESTION_EVIDENCE_INVALID',
            message='模型引用了检索结果之外的证据，请重试',
        )
    evidence = [evidence_by_id[item_id] for item_id in draft.citation_ids]
    entity_ids = list(dict.fromkeys(item.entity_id for item in evidence))
    return QuestionRead(
        id=uuid.uuid4(), question=question, supported=draft.supported,
        answer=draft.answer, confidence=draft.confidence, entity_ids=entity_ids,
        evidence=evidence, retrieval=retrieval,
        missing_information=draft.missing_information,
    )
