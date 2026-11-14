import uuid
from datetime import timezone
from itertools import zip_longest

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.domain import utc_now
from app.schemas.questions import AnswerClaim, ClaimAnswerDraft, ClaimAnswerDraftV2, EvidenceEntityRead, QuestionEvidenceRead, QuestionRead, QuestionTimeScope, RetrievalSummary
from app.llm.prompts import ANSWER_PROMPT_VERSION
from app.services import deepseek
from app.services.question_relationships import passage, relationship_passages, scoped_evidence
from app.services.projects import get_project
from app.services.question_time import resolve_question_time
from app.services.search import search_knowledge
from app.tools.evidence import EvidenceTools, payload


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
    time_scope: QuestionTimeScope | None = None,
) -> QuestionRead:
    scope = time_scope or resolve_question_time(question, valid_at, utc_now())
    if scope.valid_at is None:
        get_project(db, user_id=user_id, project_id=project_id)
        return _insufficient(
            question, scope, RetrievalSummary(keyword_hits=0, vector_hits=0, graph_hits=0,
                indexed_count=0, eligible_count=0, mode=retrieval_mode),
            '请补充一个明确的知识时点。', '在问题里写出完整日期（如 2026 年 4 月 1 日），或手动选择查询时点。',
        )
    at = scope.valid_at.astimezone(timezone.utc)

    def retrieve(query, mode):
        result = search_knowledge(
            db, user_id=user_id, project_id=project_id, query=query, types=[],
            valid_at=at, top_k=MAX_ANSWER_ENTITIES, mode=mode, settings=settings,
        )
        return collect_answer_evidence(db, user_id=user_id, project_id=project_id, at=at, result=result)

    query = retrieval_query or question
    if scope.expression:
        query = query.replace(scope.expression, ' ', 1).strip(' \t，,。:：') or query
    evidence_by_id, retrieval = retrieve(query, retrieval_mode)

    if not evidence_by_id:
        return _insufficient(
            question, scope, retrieval, '现有已确认知识中没有足够的原文证据回答这个问题。',
            '请补充并确认包含答案的项目资料。',
        )
    if settings.deepseek_api_key is None:
        raise AppError(
            status_code=503, code='QUESTION_NOT_CONFIGURED',
            message='证据问答尚未配置 DeepSeek API 密钥',
        )

    evidence_payload = [payload(item) for item in evidence_by_id.values()]
    try:
        from app.agents.registry import get_agent
        def search_more(query,mode):
            records,summary=retrieve(query,mode)
            retrieval.truncated |= summary.truncated
            return records
        tools=EvidenceTools(search_more,evidence_by_id)
        draft = get_agent('evidence_qa').run(strategy,dict(settings=settings,question=question,
            evidence=evidence_payload,conversation=context,tools=tools,code_findings=code_findings))
        retrieval.unique_evidence_count=len(evidence_by_id)
    except deepseek.QuestionError as exc:
        raise AppError(status_code=503, code=exc.code, message=exc.message) from exc

    return validated_answer(question,evidence_by_id,retrieval,draft,time_scope=scope)


def _insufficient(question, scope, retrieval, message, guidance):
    return QuestionRead(
        id=uuid.uuid4(), question=question, supported=False, answer=message, confidence=0,
        entity_ids=[], evidence=[], retrieval=retrieval, missing_information=[guidance],
        answer_protocol=ANSWER_PROMPT_VERSION, time_scope=scope,
        claims=[AnswerClaim(text=message, status='insufficient', citation_ids=[])],
    )


def collect_answer_evidence(db, *, user_id, project_id, at, result):
    records, summary = collect_evidence(result)
    relationships, truncated = scoped_evidence(db, user_id=user_id, project_id=project_id, at=at, hits=result.items)
    shared = relationship_passages(db, user_id, project_id, list(records.values()))
    passages = {passage(item): item for item in records.values()}
    for item in relationships:
        original = passages.get(passage(item))
        if original is not None:
            attributions = {entity.id: entity for entity in [*original.related_entities, *item.related_entities]}
            item.related_entities = list(attributions.values())
            item.entity_id = original.entity_id
            item.entity_name = original.entity_name
    available = {item.id: item for item in relationships}
    available.update((key, item) for key, item in records.items() if passage(item) not in shared)
    summary.truncated |= truncated or len(available) > MAX_ANSWER_EVIDENCE
    summary.unique_evidence_count = min(len(available), MAX_ANSWER_EVIDENCE)
    return dict(list(available.items())[:MAX_ANSWER_EVIDENCE]), summary


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


def validated_answer(question,evidence_by_id,retrieval,draft,*,time_scope=None):
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
        answer_protocol=(ANSWER_PROMPT_VERSION if isinstance(draft, ClaimAnswerDraft)
                         else 'evidence-claims-v2' if isinstance(draft, ClaimAnswerDraftV2) else None),
        claims=draft.claims if isinstance(draft, (ClaimAnswerDraft, ClaimAnswerDraftV2)) else None,
        time_scope=time_scope,
    )
