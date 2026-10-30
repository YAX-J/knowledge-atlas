"""Coverage and global BM25 statistics, without provider or held-out data."""
import math
import uuid

import pytest
from sqlalchemy import event, select

from app.core.config import Settings
from app.models.graph import KnowledgeEntity, KnowledgeEvidence
from app.services import deepseek, embeddings, lexical, search
from scripts.benchmark_reads import PROJECT, USER, seed
from tests.test_knowledge import configured
from tests.test_lexical_search import confirmed


def test_only_match_after_old_thousand_entity_window_is_retrieved(db_session, monkeypatch):
    seed(db_session, count=1002, history=0, body_bytes=0)
    target = db_session.scalar(select(KnowledgeEntity).where(
        KnowledgeEntity.project_id == PROJECT).order_by(KnowledgeEntity.name.desc()).limit(1))
    target.name = 'ZZZUniqueLateMatch'
    db_session.commit()
    identifier = target.id

    def forbidden(*_args, **_kwargs):
        pytest.fail('Lexical coverage must not contact a provider')
    monkeypatch.setattr(embeddings, 'embed_texts', forbidden)
    monkeypatch.setattr(deepseek, 'answer_question', forbidden)
    monkeypatch.setattr(deepseek, 'extract_candidates', forbidden)
    for mode in ('bm25', 'bm25_source'):
        result = search.search_knowledge(db_session, user_id=USER, project_id=PROJECT,
            query='ZZZUniqueLateMatch', types=[], valid_at=None, top_k=1, mode=mode,
            settings=Settings(_env_file=None))
        assert [hit.entity.id for hit in result.items] == [identifier]
        assert result.items[0].evidence
        assert result.lexical.scanned_count == result.eligible_count == 1002
        assert result.lexical.matched_count == 1
        assert not result.truncated and not result.lexical.results_truncated


def test_streamed_statistics_include_nonmatches_and_empty_documents():
    documents = [{'name': 'rare'}, {'name': 'rare common common common'}, {'name': 'common'}, {'name': ''}]
    corpus = lexical.CorpusStatistics(['rare'])
    match = None
    for document in documents:
        summary = lexical.summarize_fields(document, {'rare'})
        corpus.add(summary)
        if match is None:
            match = summary
    # n=4, df=2, average length=1.5, including the empty/unmatched documents.
    expected = math.log1p(2.5 / 2.5) * 2.2 / (1 + 1.2 * (.25 + .75 / 1.5))
    assert corpus.document_count == 4 and corpus.total_length == 6
    assert corpus.document_frequency == {'rare': 2}
    assert corpus.score(match) == pytest.approx(expected)


@pytest.mark.parametrize('mode', ['bm25', 'bm25_source'])
def test_batch_boundaries_do_not_change_scores_order_or_evidence(client, configured, monkeypatch, mode):
    project, _ = confirmed(client, monkeypatch)
    url = f'/api/v1/projects/{project}/search'
    params = {'q': 'PostgreSQL storage', 'mode': mode, 'top_k': 1}
    baseline = client.get(url, params=params).json()
    monkeypatch.setattr(search, 'BM25_BATCH_SIZE', 1)
    batched = client.get(url, params=params).json()
    assert batched['items'] == baseline['items']
    assert batched['lexical']['scanned_count'] == baseline['lexical']['scanned_count'] == 2
    assert batched['lexical']['matched_count'] == 2
    assert batched['lexical']['results_truncated']
    assert batched['lexical']['truncated_reasons'] == []


def test_equal_names_page_by_uuid_without_skips(client, db_session, configured, monkeypatch):
    project, _ = confirmed(client, monkeypatch)
    entities = list(db_session.scalars(select(KnowledgeEntity).where(
        KnowledgeEntity.project_id == uuid.UUID(project))))
    for entity in entities:
        entity.name = 'SameName'
        entity.summary = 'same summary'
    db_session.commit()
    monkeypatch.setattr(search, 'BM25_BATCH_SIZE', 1)
    response = client.get(f'/api/v1/projects/{project}/search', params={'q': 'SameName', 'mode': 'bm25'})
    assert response.status_code == 200, response.text
    data = response.json()
    assert [item['entity']['id'] for item in data['items']] == sorted(str(entity.id) for entity in entities)
    assert data['lexical']['scanned_count'] == 2 and not data['truncated']


def test_evidence_budget_is_per_entity_and_top_k_is_separate(client, db_session, configured, monkeypatch):
    project, _ = confirmed(client, monkeypatch)
    original = db_session.scalar(select(KnowledgeEvidence).where(
        KnowledgeEvidence.project_id == uuid.UUID(project), KnowledgeEvidence.entity_id.is_not(None)))
    db_session.add(KnowledgeEvidence(id=uuid.uuid4(), user_id=original.user_id, project_id=original.project_id,
        source_id=original.source_id, chunk_id=original.chunk_id, entity_id=original.entity_id,
        quote=original.quote, start_line=original.start_line, end_line=original.end_line,
        heading_path=original.heading_path))
    db_session.commit()
    monkeypatch.setattr(search, 'BM25_EVIDENCE_LIMIT', 1)
    url = f'/api/v1/projects/{project}/search'
    params = {'q': 'storage', 'mode': 'bm25'}
    result = client.get(url, params=params).json()
    assert len(result['items']) == result['lexical']['matched_count'] == 2
    assert all('evidence' in hit['matched_fields'] for hit in result['items'])
    assert result['lexical']['truncated_reasons'] == ['evidence_limit']
    assert not result['lexical']['results_truncated']
    limited = client.get(url, params={**params, 'top_k': 1}).json()
    assert limited['lexical']['results_truncated']
    assert limited['lexical']['truncated_reasons'] == ['evidence_limit']


def test_batch_reads_are_bounded_and_never_select_source_bodies(client, db_session, configured, monkeypatch):
    project, _ = confirmed(client, monkeypatch)
    monkeypatch.setattr(search, 'BM25_BATCH_SIZE', 1)
    statements = []
    def capture(_connection, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)
    engine = db_session.get_bind()
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        result = client.get(f'/api/v1/projects/{project}/search', params={'q': 'storage', 'mode': 'bm25'})
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert result.status_code == 200
    assert not any('source_documents.content' in sql for sql in statements)
    pages = [sql for sql in statements if 'substr(knowledge_entities.summary' in sql]
    assert len(pages) == 2 and all('LIMIT' in sql.upper() for sql in pages)
