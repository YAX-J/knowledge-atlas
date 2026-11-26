"""Independent Chinese retrieval regressions; no held-out outputs or provider calls."""
import uuid
from datetime import timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.api.dependencies import get_current_user_id
from app.api.routes import search as routes
from app.core.config import Settings
from app.main import app
from app.models.domain import utc_now
from app.models.graph import KnowledgeEntity
from app.services import embeddings, search
from app.services.questions import _retrieval_summary
from tests.test_knowledge import configured
from tests.test_lexical_search import confirmed


def prepare(client, monkeypatch):
    project, _ = confirmed(client, monkeypatch)
    settings = Settings(_env_file=None, embedding_api_key=SecretStr('offline-only'),
        embedding_base_url='https://example.invalid', embedding_model='no-existing-index')
    monkeypatch.setattr(routes, 'get_settings', lambda: settings)
    monkeypatch.setattr(embeddings, 'embed_texts', lambda *_: pytest.fail('Empty index must stay local'))
    return project, settings, f'/api/v1/projects/{project}/search'


def test_hybrid_chinese_soft_matching_exposes_new_protocol_and_bm25(client, configured, monkeypatch):
    _, _, url = prepare(client, monkeypatch)
    query = '中文资料应该保存在哪种数据库？'
    assert client.get(url, params={'q': query, 'mode': 'keyword'}).json()['items'] == []
    response = client.get(url, params={'q': query, 'mode': 'hybrid'})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['hybrid_protocol'] == 'bm25-vector-graph-v2'
    assert data['indexed_count'] == 0
    assert data['lexical']['protocol'] == 'mixed-bm25-v2'
    hit = data['items'][0]
    assert hit['entity']['name'] == 'PostgreSQL'
    assert hit['bm25_score'] > 0 and hit['keyword_score'] is None
    assert hit['keyword_component'] == 1 and hit['hybrid_score'] == .3
    assert hit['evidence'] and hit['matched_fields'] == ['summary']
    assert data == client.get(url, params={'q': query, 'mode': 'hybrid'}).json()


def test_hybrid_scope_time_types_and_scan_limits(client, db_session, configured, monkeypatch):
    project, settings, url = prepare(client, monkeypatch)
    params = {'q': '中文资料', 'mode': 'hybrid', 'types': 'Technology'}
    assert len(client.get(url, params=params).json()['items']) == 1
    result = search.search_knowledge(db_session,user_id=db_session.scalar(select(KnowledgeEntity.user_id).where(
        KnowledgeEntity.project_id==uuid.UUID(project))), project_id=uuid.UUID(project),query=params['q'],
        types=['Technology'],valid_at=None,top_k=5,mode='hybrid',settings=settings)
    summary = _retrieval_summary(result)
    assert summary.hybrid_protocol == 'bm25-vector-graph-v2'
    assert summary.bm25_hits == 1 and summary.keyword_hits == 0
    assert client.get(url, params={**params,'types':'Decision'}).json()['items'] == []
    other = client.post('/api/v1/projects', json={'name':'Other'}).json()['id']
    assert client.get(f'/api/v1/projects/{other}/search', params=params).json()['items'] == []
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(url, params=params).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)
    entity = db_session.scalar(select(KnowledgeEntity).where(KnowledgeEntity.project_id==uuid.UUID(project),
        KnowledgeEntity.type=='Technology'))
    now=utc_now();entity.valid_from=now-timedelta(days=2);entity.valid_to=now-timedelta(days=1);db_session.commit()
    assert client.get(url, params=params).json()['items'] == []
    historical={**params,'valid_at':(now-timedelta(hours=36)).isoformat()}
    assert len(client.get(url, params=historical).json()['items']) == 1
    entity.status='archived';db_session.commit()
    assert client.get(url, params=historical).json()['items'] == []


def test_hybrid_propagates_lexical_scan_truncation(client, configured, monkeypatch):
    _, _, url = prepare(client, monkeypatch)
    monkeypatch.setattr(search,'BM25_ENTITY_LIMIT',1)
    data=client.get(url,params={'q':'中文资料','mode':'hybrid'}).json()
    assert data['truncated'] and data['lexical']['scanned_count']==1
    assert 'entity_limit' in data['lexical']['truncated_reasons']
