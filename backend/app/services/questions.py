import uuid
from itertools import zip_longest

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.questions import EvidenceEntityRead, QuestionEvidenceRead, QuestionRead, RetrievalSummary
from app.services import deepseek
from app.services.search import search_knowledge


MAX_ANSWER_ENTITIES = 5
MAX_ANSWER_EVIDENCE = 12


def _retrieval_summary(result) -> RetrievalSummary:
    return RetrievalSummary(
        keyword_hits=sum((item.keyword_score or 0) > 0 for item in result.items),
        vector_hits=sum(item.vector_score is not None for item in result.items),
        graph_hits=sum((item.graph_score or 0) > 0 for item in result.items),
        indexed_count=result.indexed_count or 0,
        eligible_count=result.eligible_count or 0,
        mode=result.mode, bm25_hits=sum((item.bm25_score or 0) > 0 for item in result.items),
        truncated=result.truncated,
    )


def answer_question(
    db: Session, *, user_id: uuid.UUID, project_id: uuid.UUID, question: str,
    valid_at, settings: Settings, retrieval_mode: str = 'rrf',
    context: list[dict] | None = None, retrieval_query: str | None = None, strategy: str = 'single_step', code_findings=None,
) -> QuestionRead:
    result = search_knowledge(
        db, user_id=user_id, project_id=project_id, query=retrieval_query or question, types=[],
        valid_at=valid_at, top_k=MAX_ANSWER_ENTITIES, mode=retrieval_mode, settings=settings,
    )
    evidence_by_id, retrieval = collect_evidence(result)

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
        'entity_names': [entity.name for entity in item.related_entities],
    } for item in evidence_by_id.values()]
    try:
        from app.agents.registry import get_agent
        from app.tools.evidence import EvidenceTools
        def search_more(query,mode):
            found=search_knowledge(db,user_id=user_id,project_id=project_id,query=query,types=[],
                valid_at=valid_at,top_k=MAX_ANSWER_ENTITIES,mode=mode,settings=settings)
            records,summary=collect_evidence(found)
            retrieval.truncated |= summary.truncated
            return records
        tools=EvidenceTools(search_more,evidence_by_id)
        draft = get_agent('evidence_qa').run(strategy,dict(settings=settings,question=question,
            evidence=evidence_payload,conversation=context,tools=tools,code_findings=code_findings))
        retrieval.unique_evidence_count=len(evidence_by_id)
    except deepseek.QuestionError as exc:
        raise AppError(status_code=503, code=exc.code, message=exc.message) from exc

    return validated_answer(question,evidence_by_id,retrieval,draft)


def collect_evidence(result):
    retrieval = _retrieval_summary(result)
    evidence_by_id: dict[uuid.UUID, QuestionEvidenceRead] = {}
    passage_ids = {}
    seen = set()
    # Give each ranked entity a turn before taking its second/third quote.
    rows = [[(hit, item) for item in hit.evidence] for hit in result.items]
    for group in zip_longest(*rows):
        for pair in group:
            if pair is None:
                continue
            hit, item = pair
            key = (item.source_id, item.chunk_id, item.start_line, item.end_line, item.quote)
            if key in seen:
                retrieval.duplicate_evidence_count += 1
                canonical = evidence_by_id.get(passage_ids.get(key))
                if canonical is not None and all(entity.id != hit.entity.id for entity in canonical.related_entities):
                    canonical.related_entities.append(EvidenceEntityRead(id=hit.entity.id, name=hit.entity.name))
                continue
            seen.add(key)
            if len(evidence_by_id) >= MAX_ANSWER_EVIDENCE:
                retrieval.truncated = True
                continue
            evidence_by_id[item.id] = QuestionEvidenceRead(
                **item.model_dump(), entity_id=hit.entity.id, entity_name=hit.entity.name,
                related_entities=[EvidenceEntityRead(id=hit.entity.id, name=hit.entity.name)],
            )
            passage_ids[key] = item.id
    retrieval.unique_evidence_count = len(evidence_by_id)

    return evidence_by_id,retrieval


def validated_answer(question,evidence_by_id,retrieval,draft):
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
