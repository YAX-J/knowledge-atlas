import uuid
from datetime import timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.api.dependencies import get_current_user_id
from app.api.routes import search as search_routes
from app.core.config import Settings
from app.main import app
from app.models.domain import Project, utc_now
from app.models.graph import KnowledgeEntity, KnowledgeRelationship
from app.services import deepseek
from app.services import embeddings
from tests.test_graph import confirm, extracted
from tests.test_knowledge import configured


def test_search_ranking_evidence_limits_and_no_model_calls(client, db_session, configured, monkeypatch):
    project_id, source, items = extracted(client, monkeypatch)
    url = f'/api/v1/projects/{project_id}/search'
    assert client.get(url, params={'q': 'postgresql'}).json()['items'] == []
    for item in sorted(items, key=lambda item: item['kind'] != 'entity'):
        confirm(client, item)
    def unexpected(*_):
        raise AssertionError('Search must not call a model')
    monkeypatch.setattr(deepseek, 'extract_candidates', unexpected)
    result = client.get(url, params={'q': '  POSTGRESQL  ', 'top_k': 1})
    assert result.status_code == 200
    data = result.json()
    assert data['query'] == 'POSTGRESQL' and data['mode'] == 'keyword' and data['truncated']
    hit = data['items'][0]
    assert hit['entity']['name'] == 'PostgreSQL' and hit['keyword_score'] >= 60
    assert hit['matched_fields'] == ['name', 'evidence']
    assert hit['evidence'][0]['source_id'] == source['source_id']
    assert hit['evidence'][0]['start_line'] == 3
    assert hit['evidence'][0]['quote'] == 'Use PostgreSQL for storage.'
    assert 'user_id' not in str(data) and 'file://' not in str(data)
    all_hits = client.get(url, params={'q': 'postgresql'}).json()
    assert len(all_hits['items']) == 2 and not all_hits['truncated']
    assert all_hits == client.get(url, params={'q': 'postgresql'}).json()
    assert client.get(url, params={'q': 'postgresql', 'types': 'Decision'}).json()['items'][0]['entity']['type'] == 'Decision'
    assert client.get(url, params={'q': 'postgresql absent'}).json()['items'] == []
    assert len(client.get(url, params={'q': 'storage'}).json()['items']) == 2


def test_search_literal_wildcards_chinese_and_multiterm(client, db_session, configured, monkeypatch):
    def names(draft):
        draft['entities'][0].update(name='save_note_100%/path', summary='管理中文资料')
        return draft
    project_id, _, items = extracted(client, monkeypatch, names)
    for item in sorted(items, key=lambda item: item['kind'] != 'entity'):
        confirm(client, item)
    url = f'/api/v1/projects/{project_id}/search'
    for term in ['%', '_', '/path', 'save_note_100%', '中文', '管理 中文', '中文 中文']:
        data = client.get(url, params={'q': term}).json()
        assert len(data['items']) == 1, term
        assert data['items'][0]['entity']['name'] == 'save_note_100%/path'
    assert client.get(url, params={'q': "' OR 1=1 --"}).json()['items'] == []
    hits = client.get(url, params={'q': 'storage'}).json()['items']
    assert next(hit for hit in hits if hit['entity']['name'].startswith('save'))['matched_fields'] == ['evidence']


def test_search_user_project_review_and_time_boundaries(client, db_session, configured, monkeypatch):
    project_id, _, items = extracted(client, monkeypatch)
    entities = [item for item in items if item['kind'] == 'entity']
    confirm(client, entities[0])
    client.post(f"/api/v1/reviews/{entities[1]['id']}/resolve", json={'action': 'reject'})
    url = f'/api/v1/projects/{project_id}/search'
    params = {'q': 'postgresql'}
    assert len(client.get(url, params=params).json()['items']) == 1
    other = client.post('/api/v1/projects', json={'name': 'Other'}).json()['id']
    assert client.get(f'/api/v1/projects/{other}/search', params=params).json()['items'] == []
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(url, params=params).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)
    node = db_session.scalar(select(KnowledgeEntity))
    now = utc_now()
    node.valid_from = now - timedelta(days=2)
    node.valid_to = now - timedelta(days=1)
    db_session.commit()
    assert client.get(url, params=params).json()['items'] == []
    historical = {**params, 'valid_at': (now - timedelta(hours=36)).isoformat()}
    assert len(client.get(url, params=historical).json()['items']) == 1
    node.status = 'archived'
    db_session.commit()
    assert client.get(url, params=historical).json()['items'] == []
    project = db_session.get(Project, uuid.UUID(project_id))
    project.archived_at = now
    db_session.commit()
    assert client.get(url, params=params).status_code == 404


def test_search_counts_matching_evidence_once_and_caps_excerpts(client, configured, monkeypatch):
    def quotes(draft):
        original = draft['entities'][0]['evidence'][0]
        draft['entities'][0]['evidence'] = [
            {**original, 'quote': quote} for quote in [
                'Use PostgreSQL for storage.', 'PostgreSQL', 'for storage.',
                'Use PostgreSQL', 'PostgreSQL for storage.',
            ]
        ]
        return draft
    project_id, _, items = extracted(client, monkeypatch, quotes)
    entity = next(item for item in items if item['name'] == 'Store knowledge')
    confirm(client, entity)
    result = client.get(f'/api/v1/projects/{project_id}/search', params={'q': 'postgresql postgresql'}).json()
    assert len(result['items']) == 1
    hit = result['items'][0]
    assert hit['keyword_score'] == 4  # summary + evidence, once per distinct term/field
    assert hit['entity']['evidence_count'] == 5
    assert len(hit['evidence']) == 3
    assert all('PostgreSQL' in evidence['quote'] for evidence in hit['evidence'])


def test_vector_index_rebuild_and_semantic_search(client, configured, monkeypatch):
    settings = Settings(
        _env_file=None,
        embedding_api_key=SecretStr('embedding-secret'),
        embedding_base_url='https://embeddings.example/v1',
        embedding_model='test-embedding-1024',
    )
    monkeypatch.setattr(search_routes, 'get_settings', lambda: settings)

    calls = []
    def fake_embeddings(_settings, texts):
        calls.append(list(texts))
        vectors = []
        for text in texts:
            vector = [0.0] * 1024
            vector[0 if text.startswith('Technology\nPostgreSQL') or text == 'durable database' else 1] = 1.0
            vectors.append(vector)
        return vectors
    monkeypatch.setattr(embeddings, 'embed_texts', fake_embeddings)

    project_id, source, items = extracted(client, monkeypatch)
    for item in sorted(items, key=lambda item: item['kind'] != 'entity'):
        confirm(client, item)
    rebuild_url = f'/api/v1/projects/{project_id}/embeddings/rebuild'
    first = client.post(rebuild_url)
    assert first.status_code == 200
    assert first.json() == {
        'model': 'test-embedding-1024', 'dimensions': 1024,
        'eligible_count': 2, 'updated_count': 2, 'reused_count': 0,
    }
    assert client.post(rebuild_url).json()['reused_count'] == 2
    assert len(calls) == 1  # Rebuild does not call the provider for unchanged content.

    result = client.get(
        f'/api/v1/projects/{project_id}/search',
        params={'q': 'durable database', 'mode': 'vector'},
    )
    assert result.status_code == 200
    data = result.json()
    assert data['mode'] == 'vector' and data['indexed_count'] == data['eligible_count'] == 2
    assert data['items'][0]['entity']['name'] == 'PostgreSQL'
    assert data['items'][0]['vector_score'] == 1.0
    assert data['items'][0]['keyword_score'] is None and data['items'][0]['matched_fields'] == []
    assert data['items'][0]['evidence'][0]['source_id'] == source['source_id']


def test_hybrid_search_fuses_keyword_vector_and_visible_graph_signals(
    client, db_session, configured, monkeypatch,
):
    settings = Settings(
        _env_file=None,
        embedding_api_key=SecretStr('embedding-secret'),
        embedding_base_url='https://embeddings.example/v1',
        embedding_model='test-embedding-1024',
    )
    monkeypatch.setattr(search_routes, 'get_settings', lambda: settings)

    def fake_embeddings(_settings, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * 1024
            vector[0 if text.startswith('Technology\nPostgreSQL') or text == 'durable database' else 1] = 1.0
            vectors.append(vector)
        return vectors
    monkeypatch.setattr(embeddings, 'embed_texts', fake_embeddings)

    project_id, _, items = extracted(client, monkeypatch)
    for item in sorted(items, key=lambda item: item['kind'] != 'entity'):
        confirm(client, item)
    client.post(f'/api/v1/projects/{project_id}/embeddings/rebuild')
    url = f'/api/v1/projects/{project_id}/search'
    result = client.get(url, params={'q': 'durable database', 'mode': 'hybrid'})
    assert result.status_code == 200
    data = result.json()
    assert data['mode'] == 'hybrid'
    assert data['weights'] == {'keyword': .3, 'vector': .4, 'graph': .3}
    assert data['indexed_count'] == data['eligible_count'] == 2
    assert [hit['entity']['name'] for hit in data['items']] == ['PostgreSQL', 'Store knowledge']
    assert data['items'][0]['hybrid_score'] == .4
    related = data['items'][1]
    assert related['keyword_score'] == 0 and related['vector_score'] == 0
    assert related['keyword_component'] == 0 and related['vector_component'] == 0
    assert related['graph_score'] == .9 and related['hybrid_score'] == .27
    assert related['graph_connections'][0]['related_entity_name'] == 'PostgreSQL'
    assert related['graph_connections'][0]['relationship_type'] == 'USES'

    edge = db_session.scalar(select(KnowledgeRelationship))
    edge.status = 'archived'
    db_session.commit()
    without_graph = client.get(url, params={'q': 'durable database', 'mode': 'hybrid'}).json()
    store = next(hit for hit in without_graph['items'] if hit['entity']['name'] == 'Store knowledge')
    assert store['graph_score'] == 0 and store['graph_connections'] == []

    edge.status = 'active'
    edge.valid_from = utc_now() + timedelta(days=1)
    db_session.commit()
    before_relation = client.get(url, params={'q': 'durable database', 'mode': 'hybrid'}).json()
    store = next(hit for hit in before_relation['items'] if hit['entity']['name'] == 'Store knowledge')
    assert store['graph_score'] == 0 and store['graph_connections'] == []


@pytest.mark.parametrize('mode', ['vector', 'hybrid'])
def test_semantic_search_requires_embedding_configuration(client, monkeypatch, mode):
    monkeypatch.setattr(search_routes, 'get_settings', lambda: Settings(_env_file=None))
    project_id = client.post('/api/v1/projects', json={'name': 'Semantic'}).json()['id']
    response = client.get(
        f'/api/v1/projects/{project_id}/search', params={'q': 'question', 'mode': mode},
    )
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'EMBEDDING_NOT_CONFIGURED'


def test_embedding_transport_rejects_zero_vectors(monkeypatch):
    settings = Settings(
        _env_file=None,
        embedding_api_key=SecretStr('embedding-secret'),
        embedding_base_url='https://embeddings.example/v1',
        embedding_model='test-embedding-1024',
    )
    class Response:
        status_code = 200
        content = b'{}'
        def json(self):
            return {'data': [{'index': 0, 'embedding': [0.0] * 1024}]}
    monkeypatch.setattr(embeddings.httpx, 'post', lambda *args, **kwargs: Response())
    with pytest.raises(embeddings.EmbeddingError) as caught:
        embeddings.embed_texts(settings, ['query'])
    assert caught.value.code == 'EMBEDDING_OUTPUT_INVALID'


@pytest.mark.parametrize('params', [
    {}, {'q': ''}, {'q': '   '}, {'q': 'a ' * 9}, {'q': 'x' * 201},
    {'q': 'x', 'mode': 'fusion'},
    {'q': 'x', 'types': 'Invented'}, {'q': 'x', 'top_k': 0}, {'q': 'x', 'top_k': 51},
    {'q': 'x', 'valid_at': '2026-10-17T00:00:00'},
])
def test_search_rejects_invalid_and_unimplemented_parameters(client, params):
    project_id = client.post('/api/v1/projects', json={'name': 'Validation'}).json()['id']
    response = client.get(f'/api/v1/projects/{project_id}/search', params=params)
    assert response.status_code == 422
    assert response.json()['error']['request_id']
