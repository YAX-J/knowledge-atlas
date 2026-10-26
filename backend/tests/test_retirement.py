import uuid
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.api.dependencies import get_current_user_id
from app.main import app
from app.models.domain import CandidateKnowledge, Project, ReviewEvent, utc_now
from app.models.graph import KnowledgeEntity, KnowledgeEvidence, KnowledgeRelationship
from app.models.retirement import KnowledgeRetirement
from app.services import graph
from tests.test_graph import confirm, extracted
from tests.test_knowledge import configured


def prepared(client, monkeypatch):
    project, source, items = extracted(client, monkeypatch)
    records = [confirm(client, item) for item in sorted(items, key=lambda item:item['kind'] != 'entity')]
    return project, records


def request(record, **changes):
    return dict(request_id=str(uuid.uuid4()), kind='entity' if record['kind'] == 'entity' else 'relationship',
        knowledge_id=record['knowledge_id'], category='correction', reason='人工核对发现此结论误确认。', **changes)


@pytest.mark.parametrize('kind', ['entity', 'relation'])
def test_retirement_preserves_audits_evidence_and_history_but_excludes_current(client, db_session, configured, monkeypatch, kind):
    project, records = prepared(client, monkeypatch)
    selected = next(item for item in records if item['kind'] == kind)
    url = f'/api/v1/projects/{project}'
    route = f"/api/v1/knowledge/{'entities' if kind == 'entity' else 'relationships'}/{selected['knowledge_id']}"
    original = client.get(route).json()
    before = utc_now().isoformat()
    counts = {model:db_session.scalar(select(func.count()).select_from(model)) for model in
        (KnowledgeEntity, KnowledgeRelationship, KnowledgeEvidence, ReviewEvent, CandidateKnowledge)}
    payload = request(selected)
    response = client.post(url + '/knowledge-retirements', json=payload)
    assert response.status_code == 200, response.text
    event = response.json()
    assert event['before']['valid_to'] is None
    assert datetime.fromisoformat(event['after']['valid_to']) == datetime.fromisoformat(event['effective_at'])
    assert event['before']['name'] == selected['name'] and 'user_id' not in str(event)
    assert client.post(url + '/knowledge-retirements', json=payload).json() == event
    assert client.get(route).status_code == 404
    historical = client.get(route, params={'valid_at':before})
    assert historical.status_code == 200 and historical.json()['evidence'] == original['evidence']
    assert client.get(route, params={'valid_at':event['effective_at']}).status_code == 404
    assert client.get(url + '/graph').json()['edges'] == []
    if kind == 'entity':
        result = client.get(url + '/search', params={'q':selected['name'], 'mode':'bm25'}).json()
        assert all(hit['entity']['id'] != selected['knowledge_id'] for hit in result['items'])
        assert any(hit['entity']['id'] == selected['knowledge_id'] for hit in client.get(url + '/search',
            params={'q':selected['name'], 'mode':'bm25', 'valid_at':before}).json()['items'])
    assert client.get(url + '/knowledge-retirements', params={'page_size':1}).json()['items'] == [event]
    assert client.get(url + '/knowledge-retirements', params={'page':2,'page_size':1}).json()['items'] == []
    assert client.post(url + '/knowledge-retirements', json={**payload,'request_id':str(uuid.uuid4())}).status_code == 409
    assert client.post(url + '/knowledge-retirements', json={**payload,'reason':'different'}).status_code == 409
    for model, count in counts.items():
        assert db_session.scalar(select(func.count()).select_from(model)) == count


def test_retirement_scope_input_validation_and_stale_relationship(client, db_session, configured, monkeypatch):
    project, records = prepared(client, monkeypatch)
    selected = next(item for item in records if item['kind'] == 'entity')
    url = f'/api/v1/projects/{project}/knowledge-retirements'
    payload = request(selected)
    for changes in ({'reason':'   '}, {'reason':'x'*2001}, {'kind':'unknown'}, {'effective_at':utc_now().isoformat()}, {'category':'auto'}):
        assert client.post(url, json={**payload,**changes}).status_code == 422
    other = client.post('/api/v1/projects', json={'name':'Other'}).json()['id']
    assert client.post(f'/api/v1/projects/{other}/knowledge-retirements', json=payload).status_code == 404
    assert client.get(f'/api/v1/projects/{other}/knowledge-retirements').json()['total'] == 0
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.post(url, json=payload).status_code == 404
        assert client.get(url).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)
    assert client.post(url,json=payload).status_code == 200
    relation = next(item for item in records if item['kind'] == 'relation')
    assert client.post(url,json=request(relation)).status_code == 409
    project_row = db_session.get(Project,uuid.UUID(project))
    project_row.archived_at=utc_now()
    db_session.commit()
    assert client.get(url).status_code == 404


def test_retirement_rolls_back_if_audit_cannot_be_written(client, db_session, configured, monkeypatch):
    project, records = prepared(client, monkeypatch)
    selected = next(item for item in records if item['kind'] == 'entity')
    apply = graph.apply_retirement
    def broken(record,event):
        apply(record,event)
        raise RuntimeError('simulated audit failure')
    monkeypatch.setattr(graph,'apply_retirement',broken)
    with pytest.raises(RuntimeError,match='simulated audit failure'):
        client.post(f'/api/v1/projects/{project}/knowledge-retirements',json=request(selected))
    assert db_session.get(KnowledgeEntity,uuid.UUID(selected['knowledge_id'])).valid_to is None
    assert db_session.scalar(select(func.count()).select_from(KnowledgeRetirement).where(
        KnowledgeRetirement.project_id == uuid.UUID(project))) == 0


def test_retired_entity_cannot_be_reintroduced_by_pending_evolution(client, configured, monkeypatch):
    from tests.test_evolution import pair, proposal
    project, old, new = pair(client,monkeypatch)
    base=f'/api/v1/projects/{project}'
    change=client.post(base+'/knowledge-changes',json=proposal(old,new)).json()
    response=client.post(base+'/knowledge-retirements',json=dict(request_id=str(uuid.uuid4()),kind='entity',
        knowledge_id=old['entity']['id'],category='obsolete',reason='原知识已不适用。'))
    assert response.status_code == 200
    assert client.post(base+f"/knowledge-changes/{change['id']}/resolve",json={'action':'confirm'}).status_code == 409
