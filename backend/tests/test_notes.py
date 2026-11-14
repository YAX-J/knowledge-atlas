"""Append-only notes, optimistic edits, immutable snapshots and scoped raw search."""
import json
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import func, select
from app.api.routes import agents as agent_routes
from app.models.notes import NoteRevision
from app.models.domain import ReviewEvent, SourceDocument
from app.services import deepseek
from tests.test_knowledge import configured
from tests.test_multi_agent import tool
from tests.test_sources import create_project

def path(project):return f'/api/v1/projects/{project}/notes'
def create(client,project,**kwargs):
    response=client.post(path(project),json=dict(request_id=str(uuid.uuid4()),title='存储决策',markdown='Use PostgreSQL.\n原始个人笔记',**kwargs))
    assert response.status_code==201,response.text
    return response.json()

def test_revision_conflict_replay_search_scope_and_snapshot(client,db_session):
    project=create_project(client);other=create_project(client)
    note=create(client,project);original=note['current'];url=path(project)+'/'+note['id']
    body=dict(request_id=str(uuid.uuid4()),expected_revision_id=original['id'],title='修订后的决策',markdown='Use PostgreSQL and pgvector.')
    saved=client.put(url,json=body)
    assert saved.status_code==200,saved.text
    assert saved.json()['number']==2 and saved.json()['parent_revision_id']==original['id']
    assert client.put(url,json=body).json()==saved.json()
    assert client.put(url,json={**body,'markdown':'tampered'}).status_code==409
    assert client.put(url,json={**body,'request_id':str(uuid.uuid4())}).json()['error']['code']=='NOTE_REVISION_CONFLICT'
    assert client.get(path(project)+'/revisions/'+original['id']).json()==original
    assert len(client.get(url+'/revisions').json())==2
    assert client.get(path(project),params={'query':'pgvector'}).json()['total']==1
    assert client.get(path(project),params={'query':'个人笔记'}).json()['total']==0
    assert client.get(path(other)+'/'+note['id']).status_code==404
    assert client.get(path(other)+'/revisions/'+original['id']).status_code==404
    first=client.post(path(project)+'/revisions/'+original['id']+'/source')
    assert first.status_code==200,first.text
    assert client.post(path(project)+'/revisions/'+original['id']+'/source').json()==first.json()
    source=db_session.get(SourceDocument,uuid.UUID(first.json()['source_id']))
    assert 'Use PostgreSQL.' in source.content and 'pgvector' not in source.content
    assert db_session.scalar(select(func.count()).select_from(NoteRevision))==2

@pytest.mark.parametrize('change',[{'title':' '},{'markdown':'a'*60001},{'user_id':str(uuid.uuid4())}])
def test_note_input_validation(client,change):
    project=create_project(client)
    assert client.post(path(project),json={**dict(request_id=str(uuid.uuid4()),title='Title',markdown='text'),**change}).status_code==422

def test_create_replays_original_identity_after_edit(client):
    project=create_project(client);body=dict(request_id=str(uuid.uuid4()),title='Title',markdown='first')
    note=client.post(path(project),json=body).json()
    saved=client.put(path(project)+'/'+note['id'],json=dict(request_id=str(uuid.uuid4()),expected_revision_id=note['current']['id'],title='Title',markdown='second'))
    assert saved.status_code==200
    assert client.post(path(project),json=body).json()['current']['markdown']=='second'
    assert client.post(path(project),json={**body,'markdown':'different'}).status_code==409


def test_note_agent_pins_revision_and_only_promotes_reviewed_knowledge(client, configured, monkeypatch, db_session):
    project = create_project(client)
    quote = '2026-03-01 起采用 PostgreSQL，上周停止使用。'
    note = client.post(path(project), json=dict(
        request_id=str(uuid.uuid4()), title='存储决策', markdown=quote,
    )).json()
    revision = note['current']
    saved = db_session.get(NoteRevision, uuid.UUID(revision['id']))
    saved.created_at = datetime(2026, 7, 15, 10, tzinfo=timezone.utc)
    db_session.commit()
    updated = client.put(f"{path(project)}/{note['id']}", json=dict(
        request_id=str(uuid.uuid4()), expected_revision_id=revision['id'],
        title='New storage decision', markdown='Use a different database.',
    ))
    assert updated.status_code == 200
    monkeypatch.setattr(agent_routes, 'get_settings', lambda: configured)
    calls = []

    def turn(_settings, messages, _tools, **_kwargs):
        message = messages[-1]
        calls.append(message['role'])
        if message['role'] == 'user':
            chunk_id = json.loads(message['content'])['chunks'][-1]['chunk_id']
            return tool('read_chunk', {'chunk_id': chunk_id})
        chunk = json.loads(message['content'])
        assert quote in chunk['content']
        assert 'a different database' not in chunk['content']
        evidence = [dict(chunk_id=chunk['chunk_id'], quote=quote)]
        if invalid_time:
            return {'content': json.dumps(dict(
                entities=[dict(local_id='decision', type='Decision', name='Storage choice', summary='Choose storage',
                               confidence=.9, evidence=evidence, temporal={'start': '2026-03-02'})],
                relations=[],
            ))}
        return {'content': json.dumps(dict(
            entities=[
                dict(local_id='decision', type='Decision', name='Storage choice', summary='Choose storage',
                     confidence=.9, evidence=evidence, temporal={'start': '2026-03-01'}),
                dict(local_id='postgres', type='Technology', name='PostgreSQL', summary='Storage database',
                     confidence=.9, evidence=evidence, temporal={'start': '2026-03-01'}),
            ],
            relations=[dict(local_id='uses', type='USES', source='decision', target='postgres',
                            summary='Use PostgreSQL for storage', confidence=.9, evidence=evidence,
                            temporal={'start': '2026-03-01', 'end': '上周'})],
        ))}

    invalid_time = True
    monkeypatch.setattr(deepseek, 'call_agent_turn', turn)
    base = f'/api/v1/projects/{project}'
    url = f'{base}/agent-runs'
    body = dict(request_id=str(uuid.uuid4()), kind='knowledge_pipeline', note_revision_id=revision['id'])
    other = create_project(client)
    assert client.post(f'/api/v1/projects/{other}/agent-runs', json=body).status_code == 404
    invalid_run = client.post(url, json={**body, 'request_id': str(uuid.uuid4())}).json()
    assert invalid_run['status'] == 'failed'
    assert invalid_run['error_code'] == 'EXTRACTION_TIME_EVIDENCE_INVALID'
    assert client.get(f'{base}/reviews').json()['total'] == 0
    invalid_time = False
    calls.clear()
    response = client.post(url, json=body)
    assert response.status_code == 200, response.text
    run = response.json()
    assert run['status'] == 'awaiting_review', run
    assert run['scope']['note_revision_id'] == revision['id']
    assert [event['status'] for event in run['events'] if event['kind'] == 'note_parsing'] == ['succeeded']
    source = client.post(f"{path(project)}/revisions/{revision['id']}/source").json()
    assert run['source_id'] == source['source_id']
    assert client.get(f"/api/v1/tasks/{source['parse_task_id']}").json()['status'] == 'succeeded'
    assert client.post(url, json=body).json() == run
    assert client.post(url, json={**body, 'note_revision_id': updated.json()['id']}).status_code == 409
    assert client.post(url, json={**body, 'source_id': source['source_id']}).status_code == 422
    assert client.get(f'{base}/graph').json()['nodes'] == []
    items = client.get(f"{base}/reviews", params={"source_id": source['source_id']}).json()['items']
    relation = next(item for item in items if item['kind'] == 'relation')
    assert relation['temporal'] == {'start': '2026-03-01', 'end': '上周'}
    assert relation['temporal_reference'] == '2026-07-15T10:00:00Z'
    assert relation['validity'] == {'valid_from': '2026-03-01T00:00:00Z', 'valid_to': '2026-07-06T00:00:00Z'}
    review = client.post(f'{base}/reviews/resolve-batch', json=dict(
        source_id=source['source_id'], review_ids=[item['id'] for item in items if item['kind'] == 'entity'],
        action='confirm',
    ))
    assert review.status_code == 200, review.text
    resolve = f"/api/v1/reviews/{relation['id']}/resolve"
    invalid_period = {'action': 'confirm', 'changes': {'validity': {
        'valid_from': '2026-02-01T00:00:00Z', 'valid_to': '2026-07-06T00:00:00Z',
    }}}
    assert client.post(resolve, json=invalid_period).json()['error']['code'] == 'REVIEW_VALIDITY_OUTSIDE_ENDPOINTS'
    corrected = {'valid_from': '2026-03-02T00:00:00Z', 'valid_to': '2026-07-07T00:00:00Z'}
    decision = {'action': 'confirm', 'changes': {'validity': corrected}}
    confirmed = client.post(resolve, json=decision)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()['validity'] == corrected
    assert client.post(resolve, json=decision).json() == confirmed.json()
    event = db_session.scalar(select(ReviewEvent).where(ReviewEvent.candidate_id == uuid.UUID(relation['id'])))
    assert event.before['validity'] == relation['validity'] and event.after['validity'] == corrected
    assert client.get(f'{base}/graph', params={'valid_at': corrected['valid_to']}).json()['edges'] == []
    graph = client.get(f'{base}/graph', params={'valid_at': corrected['valid_from']}).json()
    assert {node['name'] for node in graph['nodes']} == {'Storage choice', 'PostgreSQL'}
    assert [edge['type'] for edge in graph['edges']] == ['USES']
    detail = client.get(
        f"/api/v1/knowledge/relationships/{graph['edges'][0]['id']}", params={'valid_at': corrected['valid_from']},
    ).json()
    assert {(item['source_id'], item['quote']) for item in detail['evidence']} == {(source['source_id'], quote)}
    completed = client.post(f"{url}/{run['id']}/resume").json()
    assert completed['status'] == 'succeeded'
    assert completed['review_counts'] == {'confirmed': 3}
    assert calls == ['user', 'tool']


def test_note_agent_requires_a_saved_body(client):
    project = create_project(client)
    note = client.post(path(project), json=dict(request_id=str(uuid.uuid4()), title='Blank', markdown=' ')).json()
    response = client.post(f'/api/v1/projects/{project}/agent-runs', json=dict(
        request_id=str(uuid.uuid4()), kind='knowledge_pipeline', note_revision_id=note['current']['id'],
    ))
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'NOTE_EMPTY'
