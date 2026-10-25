import math
from collections import Counter
import uuid
from datetime import timedelta

from pydantic import SecretStr
import pytest
from sqlalchemy import select

from app.api.dependencies import get_current_user_id
from app.api.routes import search as routes
from app.core.config import Settings
from app.main import app
from app.models.domain import Project, utc_now
from app.models.graph import KnowledgeEntity
from app.services import embeddings, lexical, search
from tests.test_graph import confirm, extracted
from tests.test_knowledge import configured


def confirmed(client, monkeypatch):
    def chinese(draft):
        next(item for item in draft['entities'] if item['local_id'] == 'postgres')['summary'] = '数据库用于保存中文资料并支持证据追溯。'
        return draft
    project_id, source, items = extracted(client, monkeypatch, chinese)
    for item in sorted(items, key=lambda item: item['kind'] != 'entity'):
        confirm(client, item)
    return project_id, source


def test_mixed_tokenizer_preserves_identifiers_and_han_bigrams():
    tokens = lexical.tokenize('中文Execution_id.foo/Path 数据库')
    assert {'中', '文', '中文', 'execution_id.foo/path', 'execution', 'id', 'foo', 'path', '数据库'[:2], '据库'} <= set(tokens)
    assert not lexical.tokenize('% "/\\ -- < >')
    assert 'δοκιμή' in lexical.tokenize('ΔΟΚΙΜΉ')


def test_bm25_formula_length_normalization_and_query_deduplication():
    documents = [{'name': 'rare'}, {'name': 'rare common common common'}, {'name': 'common'}]
    terms, scores = lexical.rank_fields(documents, 'rare rare')
    inverse = math.log1p((3 - 2 + .5) / (2 + .5))
    expected = inverse * 2.2 / (1 + 1.2 * (.25 + .75 * 1 / 2))
    assert terms == ['rare'] and scores[0][0] == pytest.approx(expected)
    assert scores[0][0] > scores[1][0] > scores[2][0] == 0
    assert scores == lexical.rank_fields(documents, 'rare')[1]
    assert lexical.rank_fields([], 'rare') == (['rare'], [])
    assert lexical.rank_fields([{'name': ''}], 'rare')[1] == [(0, [])]


def test_bm25_does_not_retain_irrelevant_vocabulary_in_counters(monkeypatch):
    counters = []
    class TrackingCounter(Counter):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            counters.append(self)
    monkeypatch.setattr(lexical, 'Counter', TrackingCounter)
    terms, scores = lexical.rank_fields([{'name': 'rare', 'summary': ' '.join(f'word{i}' for i in range(1000))}], 'rare')
    assert terms == ['rare'] and scores[0][0] > 0
    assert all(set(counter) <= {'rare'} for counter in counters)


def test_bm25_handles_chinese_questions_without_changing_literal_mode(client, configured, monkeypatch):
    project_id, _ = confirmed(client, monkeypatch)
    def forbidden(*_args, **_kwargs):
        pytest.fail('Lexical search must not call embedding/model providers')
    monkeypatch.setattr(embeddings, 'embed_texts', forbidden)
    url = f'/api/v1/projects/{project_id}/search'
    query = '中文资料应该保存在哪种数据库？'
    assert client.get(url, params={'q': query}).json()['items'] == []
    response = client.get(url, params={'q': query, 'mode': 'bm25'})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['items'][0]['entity']['name'] == 'PostgreSQL'
    assert data['items'][0]['matched_fields'] == ['summary']
    assert data['items'][0]['bm25_score'] > 0
    assert data['items'][0]['keyword_score'] is None
    assert data['lexical']['protocol'] == 'mixed-bm25-v1'
    assert '资料' in data['lexical']['query_terms']
    assert data == client.get(url, params={'q': query, 'mode': 'bm25'}).json()
    assert client.get(url, params={'q': '%', 'mode': 'bm25'}).status_code == 422


def test_bm25_scope_type_time_and_archived_boundaries(client, db_session, configured, monkeypatch):
    project_id, _ = confirmed(client, monkeypatch)
    url = f'/api/v1/projects/{project_id}/search'
    params = {'q': '中文资料', 'mode': 'bm25'}
    assert client.get(url, params={**params, 'types': 'Decision'}).json()['items'] == []
    other = client.post('/api/v1/projects', json={'name': 'Other'}).json()['id']
    assert client.get(f'/api/v1/projects/{other}/search', params=params).json()['items'] == []
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(url, params=params).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)
    entity = db_session.scalar(select(KnowledgeEntity).where(KnowledgeEntity.name == 'PostgreSQL'))
    now = utc_now()
    entity.valid_from = now - timedelta(days=2)
    entity.valid_to = now - timedelta(days=1)
    db_session.commit()
    assert client.get(url, params=params).json()['items'] == []
    history = {**params, 'valid_at': (now - timedelta(hours=36)).isoformat()}
    assert len(client.get(url, params=history).json()['items']) == 1
    entity.status = 'archived'
    db_session.commit()
    assert client.get(url, params=history).json()['items'] == []
    db_session.get(Project, uuid.UUID(project_id)).archived_at = now
    db_session.commit()
    assert client.get(url, params=params).status_code == 404


@pytest.mark.parametrize('limit,reason', [('BM25_ENTITY_LIMIT', 'entity_limit'),
                                          ('BM25_EVIDENCE_LIMIT', 'evidence_limit'), ('BM25_TEXT_LIMIT', 'text_limit')])
def test_bm25_reports_scan_and_text_truncation(client, configured, monkeypatch, limit, reason):
    project_id, _ = confirmed(client, monkeypatch)
    monkeypatch.setattr(search, limit, 1)
    response = client.get(f'/api/v1/projects/{project_id}/search', params={'q': 'storage', 'mode': 'bm25'})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['truncated'] and reason in data['lexical']['truncated_reasons']


@pytest.mark.parametrize('mode', ['vector', 'hybrid'])
@pytest.mark.parametrize('with_entities', [False, True])
def test_empty_semantic_index_never_calls_provider(client, configured, monkeypatch, mode, with_entities):
    settings = Settings(_env_file=None, embedding_api_key=SecretStr('test-key'),
                        embedding_base_url='https://example.test', embedding_model='test-model')
    monkeypatch.setattr(routes, 'get_settings', lambda: settings)
    project_id = confirmed(client, monkeypatch)[0] if with_entities else client.post(
        '/api/v1/projects', json={'name': 'Empty'}).json()['id']
    def forbidden(*_args, **_kwargs):
        pytest.fail('Empty index must not spend a query embedding request')
    monkeypatch.setattr(embeddings, 'embed_texts', forbidden)
    response = client.get(f'/api/v1/projects/{project_id}/search', params={'q': 'storage', 'mode': mode})
    assert response.status_code == 200, response.text
    assert response.json()['indexed_count'] == 0
    assert response.json()['eligible_count'] == (2 if with_entities else 0)
