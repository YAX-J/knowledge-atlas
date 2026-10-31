"""Append-only notes, optimistic edits, immutable snapshots and scoped raw search."""
import uuid
import pytest
from sqlalchemy import func, select
from app.models.notes import NoteRevision
from app.models.domain import SourceDocument
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
