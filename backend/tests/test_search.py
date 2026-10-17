import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.api.dependencies import get_current_user_id
from app.main import app
from app.models.domain import Project, utc_now
from app.models.graph import KnowledgeEntity
from app.services import deepseek
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


@pytest.mark.parametrize('params', [
    {}, {'q': ''}, {'q': '   '}, {'q': 'a ' * 9}, {'q': 'x' * 201},
    {'q': 'x', 'mode': 'vector'}, {'q': 'x', 'mode': 'hybrid'},
    {'q': 'x', 'types': 'Invented'}, {'q': 'x', 'top_k': 0}, {'q': 'x', 'top_k': 51},
    {'q': 'x', 'valid_at': '2026-10-17T00:00:00'},
])
def test_search_rejects_invalid_and_unimplemented_parameters(client, params):
    project_id = client.post('/api/v1/projects', json={'name': 'Validation'}).json()['id']
    response = client.get(f'/api/v1/projects/{project_id}/search', params=params)
    assert response.status_code == 422
    assert response.json()['error']['request_id']
