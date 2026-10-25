import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.api.dependencies import get_current_user_id
from app.api.routes import search as routes
from app.core.config import Settings
from app.main import app
from app.models.domain import Project, utc_now
from app.models.graph import KnowledgeEntity
from app.services import embeddings
from tests.test_knowledge import configured
from tests.test_questions import prepared_project


def test_status_is_provider_free_and_reports_missing_without_configuration(client, monkeypatch):
    monkeypatch.setattr(routes, 'get_settings', lambda: Settings(_env_file=None))
    monkeypatch.setattr(embeddings, 'embed_texts', lambda *_: pytest.fail('Status must be read-only and free'))
    project = client.post('/api/v1/projects', json={'name': 'Empty'}).json()['id']
    data = client.get(f'/api/v1/projects/{project}/embeddings/status').json()
    assert not data['configured'] and data['eligible_count'] == data['indexed_count'] == data['missing_count'] == 0
    assert data['scanned_count'] == data['stale_count'] == 0 and not data['truncated']


def test_status_checks_content_hashes_and_model_identity(client, db_session, configured, monkeypatch):
    project, settings = prepared_project(client, monkeypatch)
    monkeypatch.setattr(embeddings, 'embed_texts', lambda *_: pytest.fail('No provider calls'))
    url = f'/api/v1/projects/{project}/embeddings/status'
    first = client.get(url).json()
    assert first['configured'] and first['current_count'] == first['indexed_count'] == first['eligible_count'] == 2
    assert first['missing_count'] == first['stale_count'] == 0
    entity = db_session.scalar(select(KnowledgeEntity).where(KnowledgeEntity.project_id == uuid.UUID(project)))
    entity.summary += ' Updated conclusion.'
    db_session.commit()
    changed = client.get(url).json()
    assert changed['current_count'] == changed['stale_count'] == 1
    assert changed['indexed_count'] == 2  # Count alone cannot detect stale content.
    settings.embedding_model = 'another-model'
    different = client.get(url).json()
    assert different['missing_count'] == 2 and different['indexed_count'] == 0
    assert different['current_count'] == different['stale_count'] == 0


def test_status_time_project_user_and_archive_boundaries(client, db_session, configured, monkeypatch):
    project, _ = prepared_project(client, monkeypatch)
    url = f'/api/v1/projects/{project}/embeddings/status'
    entity = db_session.scalar(select(KnowledgeEntity).where(KnowledgeEntity.project_id == uuid.UUID(project)))
    now = utc_now()
    entity.valid_from, entity.valid_to = now-timedelta(days=2), now-timedelta(days=1)
    db_session.commit()
    assert client.get(url).json()['eligible_count'] == 1
    history = client.get(url, params={'valid_at': (now-timedelta(hours=36)).isoformat()}).json()
    assert history['eligible_count'] == history['indexed_count'] == 1
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(url).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)
    other = client.post('/api/v1/projects', json={'name': 'Other'}).json()['id']
    assert client.get(f'/api/v1/projects/{other}/embeddings/status').json()['eligible_count'] == 0
    db_session.get(Project, uuid.UUID(project)).archived_at = now
    db_session.commit()
    assert client.get(url).status_code == 404


def test_status_reports_bounded_inspection(client, configured, monkeypatch):
    project, _ = prepared_project(client, monkeypatch)
    monkeypatch.setattr(embeddings, 'INDEX_STATUS_SCAN_LIMIT', 1)
    data = client.get(f'/api/v1/projects/{project}/embeddings/status').json()
    assert data['indexed_count'] == data['eligible_count'] == 2
    assert data['scanned_count'] == data['scan_limit'] == 1 and data['truncated']
    assert data['current_count'] == 1
