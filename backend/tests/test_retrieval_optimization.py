import uuid
from datetime import timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.api.dependencies import get_current_user_id
from app.api.routes import questions as question_routes, search as search_routes
from app.core.config import Settings
from app.main import app
from app.models.domain import utc_now
from app.models.graph import KnowledgeEntity
from app.schemas.questions import AnswerDraft
from app.services import deepseek, embeddings, fusion, search
from tests.test_graph import confirm, extracted
from tests.test_knowledge import configured
from tests.test_questions import prepared_project


def test_rrf_combines_ranks_and_keeps_legacy_modes(client, configured, monkeypatch):
    project, _ = prepared_project(client, monkeypatch)
    url = f'/api/v1/projects/{project}/search'
    legacy = client.get(url, params={'q': 'PostgreSQL', 'mode': 'hybrid'}).json()
    data = client.get(url, params={'q': 'PostgreSQL', 'mode': 'rrf'}).json()
    assert data['mode'] == 'rrf' and data['weights'] is None
    assert data['lexical']['protocol'] == 'mixed-bm25-v2'
    assert data['indexed_count'] == data['eligible_count'] == 2
    for hit in data['items']:
        expected = sum(1 / (60 + hit[key]) for key in ('lexical_rank', 'vector_rank') if hit[key])
        assert hit['rrf_score'] == pytest.approx(expected)
        assert hit['graph_connections'] == [] and hit['graph_score'] is None
        assert hit['evidence']
    assert data == client.get(url, params={'q': 'PostgreSQL', 'mode': 'rrf'}).json()
    assert legacy == client.get(url, params={'q': 'PostgreSQL', 'mode': 'hybrid'}).json()
    limited = client.get(url, params={'q': 'PostgreSQL', 'mode': 'rrf', 'top_k': 1}).json()
    assert len(limited['items']) == 1 and limited['truncated']


def test_rrf_no_graph_expansion_and_reports_scan_budget(client, configured, monkeypatch):
    project, _ = prepared_project(client, monkeypatch)
    monkeypatch.setattr(fusion, 'RRF_POOL_LIMIT', 1)
    monkeypatch.setattr(search, 'BM25_ENTITY_LIMIT', 1)
    data = client.get(f'/api/v1/projects/{project}/search', params={'q': 'PostgreSQL', 'mode': 'rrf'}).json()
    assert data['truncated'] and 'entity_limit' in data['lexical']['truncated_reasons']
    assert all(not item['graph_connections'] for item in data['items'])


def test_rrf_scope_type_history_and_archive(client, db_session, configured, monkeypatch):
    project, _ = prepared_project(client, monkeypatch)
    url = f'/api/v1/projects/{project}/search'
    params = {'q': 'database', 'mode': 'rrf', 'types': 'Technology'}
    assert len(client.get(url, params=params).json()['items']) == 1
    other = client.post('/api/v1/projects', json={'name': 'Other'}).json()['id']
    assert client.get(f'/api/v1/projects/{other}/search', params=params).json()['items'] == []
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(url, params=params).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)
    entity = db_session.scalar(select(KnowledgeEntity).where(
        KnowledgeEntity.type == 'Technology', KnowledgeEntity.project_id == uuid.UUID(project)))
    now = utc_now()
    entity.valid_from, entity.valid_to = now - timedelta(days=2), now - timedelta(days=1)
    db_session.commit()
    assert client.get(url, params=params).json()['items'] == []
    history = {**params, 'valid_at': (now - timedelta(hours=36)).isoformat()}
    assert len(client.get(url, params=history).json()['items']) == 1
    entity.status = 'archived'
    db_session.commit()
    assert client.get(url, params=history).json()['items'] == []


def test_rrf_empty_index_does_not_call_provider_but_requires_configuration(client, configured, monkeypatch):
    project, _, items = extracted(client, monkeypatch)
    for item in items:
        if item['kind'] == 'entity':
            confirm(client, item)
    settings = Settings(_env_file=None, embedding_api_key=SecretStr('test'),
                        embedding_base_url='https://example.test', embedding_model='test-1024')
    monkeypatch.setattr(search_routes, 'get_settings', lambda: settings)
    monkeypatch.setattr(embeddings, 'embed_texts', lambda *_: pytest.fail('Empty index must stay local'))
    url = f'/api/v1/projects/{project}/search'
    data = client.get(url, params={'q': 'PostgreSQL', 'mode': 'rrf'}).json()
    assert data['items'] and data['indexed_count'] == 0
    assert all(hit['vector_rank'] is None for hit in data['items'])
    settings.embedding_api_key = None
    assert client.get(url, params={'q': 'PostgreSQL', 'mode': 'rrf'}).status_code == 503


@pytest.mark.parametrize('mode', ['hybrid', 'rrf', 'vector', 'bm25'])
def test_question_modes_deduplicate_same_source_evidence(client, configured, monkeypatch, mode):
    project, settings = prepared_project(client, monkeypatch)
    if mode == 'bm25':
        settings.embedding_api_key = None
        monkeypatch.setattr(embeddings, 'embed_texts', lambda *_: pytest.fail('BM25 must not request embeddings'))
    seen = []
    def answer(_settings, _question, evidence):
        seen.extend(evidence)
        assert len(evidence) == 1
        return AnswerDraft(supported=True, answer='PostgreSQL', confidence=.8,
                           citation_ids=[evidence[0]['id']], missing_information=[])
    monkeypatch.setattr(deepseek, 'answer_question', answer)
    response = client.post(f'/api/v1/projects/{project}/questions', json={
        'question': 'PostgreSQL storage', 'retrieval_mode': mode})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['retrieval']['mode'] == mode
    assert result['retrieval']['unique_evidence_count'] == 1
    assert result['retrieval']['duplicate_evidence_count'] == 1
    assert result['evidence'][0]['id'] == seen[0]['id']


def test_bm25_no_evidence_needs_no_model_configuration(client, monkeypatch):
    monkeypatch.setattr(question_routes, 'get_settings', lambda: Settings(_env_file=None))
    monkeypatch.setattr(deepseek, 'answer_question', lambda *_: pytest.fail('No evidence'))
    project = client.post('/api/v1/projects', json={'name': 'Empty'}).json()['id']
    response = client.post(f'/api/v1/projects/{project}/questions', json={
        'question': 'missing information', 'retrieval_mode': 'bm25'})
    assert response.status_code == 200 and not response.json()['supported']
    assert client.post(f'/api/v1/projects/{project}/questions', json={
        'question': 'question', 'retrieval_mode': 'unrecognized'}).status_code == 422
