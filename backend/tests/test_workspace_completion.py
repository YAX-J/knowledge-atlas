import uuid
from sqlalchemy import func, select
from app.models.domain import utc_now
from app.models.graph import KnowledgeEvidence
from app.models.workspace import KnowledgeOperation
from tests.test_evolution import pair, reviewed_decision
from tests.test_knowledge import configured
from tests.test_retirement import prepared


def operation(client, project, entity, action, **kwargs):
    body = dict(request_id=str(uuid.uuid4()), knowledge_id=entity, action=action,
                reason='人工核对原始证据。', **kwargs)
    response = client.post(f'/api/v1/projects/{project}/knowledge-operations', json=body)
    assert response.status_code == 200, response.text
    return response.json(), body


def test_alias_merge_unmerge_preserve_history_quotes_and_scope(client, db_session, configured, monkeypatch):
    project, old, new = pair(client, monkeypatch)
    old_id, new_id = old['entity']['id'], new['entity']['id']
    base = f'/api/v1/projects/{project}'
    before = utc_now().isoformat()
    count = db_session.scalar(select(func.count()).select_from(KnowledgeEvidence))
    operation(client, project, old_id, 'alias', alias='LegacyCache')
    event, body = operation(client, project, old_id, 'merge', target_id=new_id)
    assert client.post(base+'/knowledge-operations', json=body).json() == event
    assert client.post(base+'/knowledge-operations', json={**body, 'reason':'changed'}).status_code == 409
    assert [n['id'] for n in client.get(base+'/graph').json()['nodes']] == [new_id]
    assert len(client.get(base+'/graph', params={'valid_at':before}).json()['nodes']) == 2
    detail = client.get(f'/api/v1/knowledge/entities/{new_id}').json()
    assert {e['id'] for e in detail['evidence']} == {e['id'] for d in (old,new) for e in d['evidence']}
    assert len(client.get(f'/api/v1/knowledge/entities/{new_id}', params={'valid_at':before}).json()['evidence']) == 1
    for mode in ('keyword', 'bm25', 'bm25_source'):
        hits = client.get(base+'/search', params={'q':'LegacyCache', 'mode':mode})
        assert hits.status_code == 200, hits.text
        assert hits.json()['items'][0]['entity']['id'] == new_id
    assert client.get(base+f'/knowledge/entities/{old_id}/identity').json()['canonical_id'] == new_id
    other = client.post('/api/v1/projects', json={'name':'Other'}).json()['id']
    assert client.post(f'/api/v1/projects/{other}/knowledge-operations', json=body).status_code == 404
    operation(client, project, old_id, 'unmerge')
    assert len(client.get(base+'/graph').json()['nodes']) == 2
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEvidence)) == count


def test_withdraw_reactivate_preserve_gap_and_old_interval(client, configured, monkeypatch):
    project, records = prepared(client, monkeypatch)
    entity = next(item for item in records if item['kind']=='entity')['knowledge_id']
    route = f'/api/v1/knowledge/entities/{entity}'
    before = utc_now().isoformat()
    event, _ = operation(client, project, entity, 'withdraw')
    gap = utc_now().isoformat()
    assert client.get(route).status_code == 404
    operation(client, project, entity, 'reactivate')
    assert client.get(route).status_code == 200
    assert client.get(route, params={'valid_at':before}).status_code == 200
    assert client.get(route, params={'valid_at':gap}).status_code == 404
    operation(client, project, entity, 'withdraw')
    assert client.get(route, params={'valid_at':before}).status_code == 200


def test_merge_projects_edges_to_canonical_without_mutating_original(client, db_session, configured, monkeypatch):
    from app.models.graph import KnowledgeEntity, KnowledgeRelationship
    project, records = prepared(client, monkeypatch)
    old = next(item for item in records if item['kind']=='entity')
    new = reviewed_decision(client, monkeypatch, project, 3)
    row = db_session.get(KnowledgeEntity, uuid.UUID(old['knowledge_id']))
    row.type = 'Decision'
    db_session.commit()
    original = client.get(f'/api/v1/projects/{project}/graph').json()['edges'][0]
    operation(client, project, old['knowledge_id'], 'merge', target_id=new['entity']['id'])
    edges = client.get(f'/api/v1/projects/{project}/graph').json()['edges']
    assert len(edges)==1
    assert new['entity']['id'] in (edges[0]['source_id'], edges[0]['target_id'])
    stored = db_session.get(KnowledgeRelationship, uuid.UUID(original['id']))
    assert str(stored.source_id)==original['source_id'] and str(stored.target_id)==original['target_id']


def test_reviewed_branch_group_and_reverse_linear_change_keep_history(client, configured, monkeypatch):
    from tests.test_evolution import proposal, propose, resolve
    project,old,new=pair(client,monkeypatch)
    base=f'/api/v1/projects/{project}'
    change=propose(client,project,proposal(old,new))
    assert resolve(client,project,change).status_code==200
    before=utc_now().isoformat()
    operation(client,project,change['id'],'reverse_change')
    assert [item['id'] for item in client.get(base+'/graph').json()['nodes']]==[old['entity']['id']]
    assert [item['id'] for item in client.get(base+'/graph',params={'valid_at':before}).json()['nodes']]==[new['entity']['id']]
    second=reviewed_decision(client,monkeypatch,project,3)
    third=reviewed_decision(client,monkeypatch,project,4)
    payload=dict(request_id=str(uuid.uuid4()),old_entity_ids=[old['entity']['id']],
        new_entity_ids=[second['entity']['id'],third['entity']['id']],reason='原方案拆分为两个独立责任。')
    group=client.post(base+'/knowledge-change-groups',json=payload)
    assert group.status_code==200,group.text
    assert client.post(base+'/knowledge-change-groups',json=payload).json()==group.json()
    assert {item['id'] for item in client.get(base+'/graph').json()['nodes']}=={second['entity']['id'],third['entity']['id']}
    assert len(client.get(base+f"/knowledge/entities/{old['entity']['id']}/history").json()['changes'])==3


def test_vectors_project_original_members_without_leaking_future_merge_into_history(client, db_session, configured, monkeypatch):
    from app.core.config import Settings
    from app.core.identity import DEVELOPMENT_USER_ID
    from app.models.graph import KnowledgeEmbedding, KnowledgeEntity
    from app.services import embeddings, search
    project,old,new=pair(client,monkeypatch)
    old_id,new_id=uuid.UUID(old['entity']['id']),uuid.UUID(new['entity']['id'])
    settings=Settings(_env_file=None,embedding_api_key='synthetic',embedding_base_url='https://example.test/v1',embedding_model='synthetic')
    for entity_id,vector in ((old_id,[1.,0.]),(new_id,[0.,1.])):
        db_session.add(KnowledgeEmbedding(entity_id=entity_id,user_id=DEVELOPMENT_USER_ID,project_id=uuid.UUID(project),
            model='synthetic',dimensions=1024,content_sha256='0'*64,embedding=vector+[0.]*1022))
    db_session.commit()
    before=utc_now()
    operation(client,project,str(old_id),'merge',target_id=str(new_id))
    monkeypatch.setattr(embeddings,'embed_texts',lambda *_:[[1.,0.]+[0.]*1022])
    def retrieve(at):
        return search.search_knowledge(db_session,user_id=DEVELOPMENT_USER_ID,project_id=uuid.UUID(project),query='old version',
            types=[],valid_at=at,top_k=5,mode='vector',settings=settings)
    current=retrieve(None)
    assert len(current.items)==1 and current.items[0].entity.id==new_id and current.items[0].vector_score==1
    past=retrieve(before)
    assert {item.entity.id:item.vector_score for item in past.items}=={old_id:1.,new_id:0.}
    assert len(next(item for item in past.items if item.entity.id==new_id).evidence)==1
    # Index inspection must agree with retrieval even when only a merged member has a vector.
    db_session.delete(db_session.get(KnowledgeEmbedding,new_id));db_session.commit()
    status=embeddings.project_embedding_status(db_session,user_id=DEVELOPMENT_USER_ID,project_id=uuid.UUID(project),settings=settings)
    assert status.indexed_count==status.eligible_count==1 and status.missing_count==0 and status.stale_count==1


def test_ambiguous_identity_and_invalid_groups_are_atomic(client, db_session, configured, monkeypatch):
    from app.models.graph import KnowledgeEntity
    project,old,new=pair(client,monkeypatch)
    base=f'/api/v1/projects/{project}'
    old_id,new_id=old['entity']['id'],new['entity']['id']
    row=db_session.get(KnowledgeEntity,uuid.UUID(new_id)); row.name='ＦｕｌｌＷｉｄｔｈ';db_session.commit()
    payload=dict(request_id=str(uuid.uuid4()),knowledge_id=old_id,action='alias',reason='Check Unicode identity',alias='fullwidth')
    response=client.post(base+'/knowledge-operations',json=payload)
    assert response.status_code==409 and response.json()['error']['code']=='ALIAS_AMBIGUOUS'
    assert client.get(base+'/knowledge-operations').json()['total']==0
    for old_ids,new_ids in (([old_id],[old_id]),([old_id,old_id],[new_id]),([old_id],[str(uuid.uuid4())])):
        response=client.post(base+'/knowledge-change-groups',json=dict(request_id=str(uuid.uuid4()),
            old_entity_ids=old_ids,new_entity_ids=new_ids,reason='Invalid group cannot partially mutate'))
        assert response.status_code==409,response.text
    assert len(client.get(base+'/graph').json()['nodes'])==2
    overview=client.get(base+'/overview')
    assert overview.status_code==200 and overview.json()['entities']==2
    assert client.get(base+'/knowledge-operations').json()['total']==0


def test_normalized_alias_bounds_and_merge_chain_retrieval(client, db_session, configured, monkeypatch):
    project,old,new=pair(client,monkeypatch)
    third=reviewed_decision(client,monkeypatch,project,3)
    base=f'/api/v1/projects/{project}'
    old_id,new_id,third_id=old['entity']['id'],new['entity']['id'],third['entity']['id']
    response=client.post(base+'/knowledge-operations',json=dict(request_id=str(uuid.uuid4()),knowledge_id=old_id,
        action='alias',alias='ß'*255,reason='Expansion must fail before persistence'))
    assert response.status_code==422
    operation(client,project,old_id,'alias',alias='Ｓｈａｒｅｄ Identity')
    conflict=client.post(base+'/knowledge-operations',json=dict(request_id=str(uuid.uuid4()),knowledge_id=new_id,
        action='alias',alias='shared identity',reason='Casefold collision'))
    assert conflict.status_code==409 and conflict.json()['error']['code']=='ALIAS_AMBIGUOUS'
    operation(client,project,old_id,'merge',target_id=new_id)
    operation(client,project,new_id,'merge',target_id=third_id)
    assert set(client.get(base+f'/knowledge/entities/{third_id}/identity').json()['member_ids'])=={old_id,new_id,third_id}
    for mode in ('keyword','bm25','bm25_source'):
        result=client.get(base+'/search',params={'q':'Identity','mode':mode})
        assert result.status_code==200 and result.json()['items'][0]['entity']['id']==third_id
    operation(client,project,old_id,'unmerge')
    for mode in ('keyword','bm25','bm25_source'):
        result=client.get(base+'/search',params={'q':'Identity','mode':mode})
        assert result.json()['items'][0]['entity']['id']==old_id
    from app.models.graph import KnowledgeEntity
    db_session.get(KnowledgeEntity,uuid.UUID(new_id)).name='ß'*255
    db_session.commit()
    operation(client,project,new_id,'unmerge')
    failed=client.post(base+'/knowledge-operations',json=dict(request_id=str(uuid.uuid4()),knowledge_id=new_id,
        action='merge',target_id=third_id,reason='Long canonical alias must roll back safely'))
    assert failed.status_code==409 and failed.json()['error']['code']=='MERGE_ALIAS_TOO_LONG'
