"""Compare the evidence before and after a reviewed relationship replacement."""

import re
from datetime import timedelta

from sqlalchemy import select

from app.core.names import normalize_name
from app.models.domain import ReviewEvent
from app.models.graph import KnowledgeEntity, KnowledgeRelationship
from app.schemas.graph import KnowledgeEdgeRead
from app.schemas.questions import QuestionComparisonRead
from app.services import graph
from app.services.question_relationships import edge_evidence
from app.services.question_time import CUTOVER, DATE_OR_DAY, GENERIC_CUTOVER, comparison_dates, uses_reviewed_cutover


MAX_REVIEWED_REPLACEMENTS = 100
DATABASE = re.compile(r'数据库|主库|\bdatabase\b', re.I)


def compare_replacement(db, user_id, project_id, question):
    dates = comparison_dates(question)
    if dates is None and not uses_reviewed_cutover(question):
        return None, [], '请在问题中写出两个不同的完整日期和要对比的实体名称。', False

    receipt = ReviewEvent.after['replacement']
    events = list(db.scalars(select(ReviewEvent).where(
        ReviewEvent.user_id == user_id, ReviewEvent.project_id == project_id,
        ReviewEvent.action == 'confirm', receipt['kind'].as_string() == 'SUPERSEDES',
    ).order_by(ReviewEvent.id).limit(MAX_REVIEWED_REPLACEMENTS + 1)))
    if len(events) > MAX_REVIEWED_REPLACEMENTS:
        return None, [], '已审核替代记录超过本次对比范围。请在知识演进中查看记录。', True
    pairs = []
    for event in events:
        replacement = event.after['replacement']
        old = KnowledgeEdgeRead.model_validate(replacement['old'])
        new = KnowledgeEdgeRead.model_validate(replacement['new'])
        if old.valid_to == new.valid_from and (dates is None or dates[0] < new.valid_from <= dates[1]):
            pairs.append((old, new))

    name_query = normalize_name(DATE_OR_DAY.sub(' ', question))
    names = dict(db.execute(select(KnowledgeEntity.id, KnowledgeEntity.name).where(
        KnowledgeEntity.user_id == user_id, KnowledgeEntity.project_id == project_id,
        KnowledgeEntity.id.in_({old.source_id for old, _ in pairs}),
    )).all()) if pairs else {}
    # Unnamed requests may use a unique project cutover. Named requests must match the audited subject.
    if not (dates is None and GENERIC_CUTOVER.fullmatch(name_query)):
        pairs = [(old, new) for old, new in pairs if _matches_question(name_query, names.get(old.source_id))]
    if len(pairs) != 1:
        guidance = ('找到多条可能的切换记录。请补充实体名称和切换两侧的完整日期。' if len(pairs) > 1
                    else '请核对实体名称和日期，并确认该时段内有已审核的关系替代记录。')
        return None, [], guidance, False

    old, new = pairs[0]
    cutover = new.valid_from
    before_at, after_at = dates or (cutover - timedelta(microseconds=1), cutover)
    records = []
    for at, expected in [(before_at, old.id), (after_at, new.id)]:
        visible = list(db.scalars(graph._edge_query(user_id, project_id, at).where(
            KnowledgeRelationship.id.in_([old.id, new.id]),
        )))
        if len(visible) != 1 or visible[0].id != expected:
            return None, [], '这两个时点未能分别确认替代前后的关系。请选取更接近切换日期的两个时点。', False
        evidence = edge_evidence(db, visible, user_id, project_id, at)
        if not evidence:
            return None, [], '切换前后都需要保留可定位到原文的证据。', False
        records.append(evidence[0])

    before, after = records
    return QuestionComparisonRead(
        source='dates' if dates else 'replacement', before_at=before_at, after_at=after_at,
        cutover_at=cutover, before_citation_id=before.id, after_citation_id=after.id,
    ), records, None, False


def _matches_question(question: str, name: str | None) -> bool:
    if not name:
        return False
    subject = normalize_name(name)
    if question.startswith(subject) and GENERIC_CUTOVER.fullmatch(question[len(subject):].strip()) and CUTOVER.search(question):
        return True
    if not DATABASE.search(question):
        return False
    if subject and subject.isascii():
        return bool(re.search(rf'(?<![a-z0-9]){re.escape(subject)}(?![a-z0-9])', question))
    return bool(subject and subject in question)
