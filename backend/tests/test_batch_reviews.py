import uuid

import pytest
from sqlalchemy import func, select

from app.api.dependencies import get_current_user_id
from app.main import app
from app.models.domain import CandidateKnowledge, ReviewEvent, ReviewStatus
from app.models.graph import KnowledgeEntity, KnowledgeRelationship
from tests.test_graph import confirm, extracted
from tests.test_knowledge import configured


def submit(client, project, source, items, action='confirm'):
    return client.post(f'/api/v1/projects/{project}/reviews/resolve-batch', json={
        'source_id': source['source_id'], 'review_ids': [item['id'] for item in items], 'action': action})


def test_batch_handles_reverse_dependencies_and_is_idempotent(client, db_session, configured, monkeypatch):
    project, source, items = extracted(client, monkeypatch)
    ordered = sorted(items, key=lambda item: item['kind'] == 'entity')
    response = submit(client, project, source, ordered)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['processed_count'] == 3
    assert [item['id'] for item in result['items']] == [item['id'] for item in ordered]
    assert all(item['review_status'] == 'confirmed' and item['knowledge_id'] for item in result['items'])
    assert submit(client, project, source, ordered).json() == result
    assert db_session.scalar(select(func.count()).select_from(ReviewEvent).where(ReviewEvent.project_id == uuid.UUID(project))) == 3
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEntity).where(KnowledgeEntity.project_id == uuid.UUID(project))) == 2
    assert db_session.scalar(select(func.count()).select_from(KnowledgeRelationship).where(KnowledgeRelationship.project_id == uuid.UUID(project))) == 1


def test_unconfirmed_endpoint_rolls_back_whole_batch(client, db_session, configured, monkeypatch):
    project, source, items = extracted(client, monkeypatch)
    entity = next(item for item in items if item['kind'] == 'entity')
    relation = next(item for item in items if item['kind'] == 'relation')
    response = submit(client, project, source, [relation, entity])
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'REVIEW_ENDPOINTS_UNCONFIRMED'
    assert all(item.review_status == ReviewStatus.PENDING for item in db_session.scalars(
        select(CandidateKnowledge).where(CandidateKnowledge.project_id == uuid.UUID(project))))
    assert db_session.scalar(select(func.count()).select_from(ReviewEvent).where(ReviewEvent.project_id == uuid.UUID(project))) == 0
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEntity).where(KnowledgeEntity.project_id == uuid.UUID(project))) == 0


def test_batch_rejection_and_conflicting_replay(client, db_session, configured, monkeypatch):
    project, source, items = extracted(client, monkeypatch)
    first = submit(client, project, source, items, 'reject')
    assert first.status_code == 200
    assert submit(client, project, source, items, 'reject').json() == first.json()
    assert submit(client, project, source, items).status_code == 409
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEntity).where(KnowledgeEntity.project_id == uuid.UUID(project))) == 0


def test_invalid_relation_evidence_rolls_back_promoted_entities_and_audits(client, db_session, configured, monkeypatch):
    project, source, items = extracted(client, monkeypatch)
    relation = next(item for item in items if item['kind'] == 'relation')
    record = db_session.get(CandidateKnowledge, uuid.UUID(relation['id']))
    record.payload = {**record.payload, 'evidence': [{**record.payload['evidence'][0], 'quote': 'Invented evidence'}]}
    db_session.commit()
    response = submit(client, project, source, items)
    assert response.status_code == 409
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEntity).where(KnowledgeEntity.project_id == uuid.UUID(project))) == 0
    assert db_session.scalar(select(func.count()).select_from(ReviewEvent).where(ReviewEvent.project_id == uuid.UUID(project))) == 0
    assert client.get(f"/api/v1/sources/{source['source_id']}/extraction").json()['review_counts']['pending'] == 3


def test_batch_scope_validation_never_processes_other_sources(client, configured, monkeypatch):
    project, source, items = extracted(client, monkeypatch)
    other_project, other_source, other_items = extracted(client, monkeypatch)
    assert submit(client, project, other_source, items).status_code == 404
    assert submit(client, project, source, [items[0], other_items[0]]).status_code == 404
    assert submit(client, other_project, source, items).status_code == 404
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert submit(client, project, source, items).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)
    counts = client.get(f"/api/v1/sources/{source['source_id']}/extraction").json()['review_counts']
    assert counts == {'pending': 3, 'confirmed': 0, 'rejected': 0}
    for bad in ([], [items[0], items[0]], [{'id': str(uuid.uuid4())} for _ in range(101)]):
        assert submit(client, project, source, bad).status_code == 422


def test_batch_can_include_previously_confirmed_endpoints(client, configured, monkeypatch):
    project, source, items = extracted(client, monkeypatch)
    entity = next(item for item in items if item['kind'] == 'entity')
    confirm(client, entity)
    assert submit(client, project, source, items).status_code == 200
