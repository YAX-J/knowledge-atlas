from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import func,select

from app.api.routes import knowledge as routes
from app.core.config import Settings
from app.models.domain import CandidateKnowledge,SourceChunk,SourceDocument
from app.models.graph import KnowledgeEntity,KnowledgeEvidence
from app.schemas.knowledge import ExtractionDraft
from app.services import deepseek
from app.services.extraction_batches import build_plan
from tests.test_knowledge import configured
from tests.test_parsing import upload
from tests.test_sources import create_project


def prepared(client,body):
    project=create_project(client);source=upload(client,project,body.encode())
    assert client.post(f"/api/v1/tasks/{source['task_id']}/run").json()['status']=='succeeded'
    return project,source


def draft_for(chunks):
    evidence=[dict(chunk_id=chunks[0]['chunk_id'],quote=chunks[0]['content'].strip()[:80])]
    return ExtractionDraft(entities=[dict(local_id='item',type='Concept',name='Claim',summary='A source claim',confidence=.9,evidence=evidence)],relations=[])


def test_plan_covers_escaped_unicode_fragments_exactly_with_bounded_payloads():
    content=('中文 "quoted" \\ value\n'*300)
    chunk=SimpleNamespace(id=uuid.uuid4(),content=content,start_line=7,heading_path=['A'])
    source=SimpleNamespace(id=uuid.uuid4(),content_sha256='a'*64)
    settings=Settings(_env_file=None,extraction_max_input_chars=2000)
    plan=build_plan(source,[chunk],settings)
    fragments=[part for batch in plan.batches for part in batch]
    assert ''.join(part['content'] for part in fragments)==content
    assert all(size<=2000 for size in plan.public['input_chars'])
    assert 1<len(plan.batches)<=8
    assert build_plan(source,[chunk],settings).public==plan.public
    offset=0
    for fragment in fragments:
        record=plan.evidence[uuid.UUID(fragment['chunk_id'])]
        assert record['chunk_id']==chunk.id
        assert record['start_line']==7+content[:offset].count('\n')
        offset+=len(fragment['content'])


def test_long_document_preflight_is_free_bound_to_plan_and_cached_after_success(client,db_session,configured,monkeypatch):
    settings=configured.model_copy(update={'extraction_max_input_chars':2000})
    monkeypatch.setattr(routes,'get_settings',lambda:settings)
    project,source=prepared(client,'# Facts\n\n'+'\n\n'.join(f'Fact {i} is documented.' for i in range(120)))
    calls=[]
    monkeypatch.setattr(deepseek,'extract_candidates',lambda _settings,chunks:(calls.append(chunks),draft_for(chunks))[1])
    base=f"/api/v1/sources/{source['source_id']}"
    plan=client.get(base+'/extraction-plan').json()
    assert plan['batch_count']>1 and calls==[]
    assert client.post(base+'/extract').status_code==413
    assert client.post(base+'/extract?strategy=batched&plan_sha256='+'0'*64).status_code==409
    assert calls==[]
    response=client.post(base+'/extract',params={'strategy':'batched','plan_sha256':plan['plan_sha256']})
    assert response.status_code==200,response.text
    assert response.json()['task']['status']=='succeeded'
    assert len(calls)==plan['batch_count']
    assert response.json()['candidate_count']==plan['batch_count']
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEntity).where(KnowledgeEntity.project_id==uuid.UUID(project)))==0
    assert client.get(base+'/extraction-plan').json()['cached'] is True
    assert client.post(base+'/extract',params={'strategy':'batched','plan_sha256':plan['plan_sha256']}).json()==response.json()
    assert len(calls)==plan['batch_count']


def test_later_batch_failure_keeps_zero_candidates_and_stops_without_retry(client,db_session,configured,monkeypatch):
    monkeypatch.setattr(routes,'get_settings',lambda:configured.model_copy(update={'extraction_max_input_chars':1500}))
    project,source=prepared(client,'# Facts\n\n'+'\n\n'.join(f'Fact {i} is documented.' for i in range(60)))
    base=f"/api/v1/sources/{source['source_id']}";plan=client.get(base+'/extraction-plan').json()
    calls=[]
    def output(_settings,chunks):
        calls.append(chunks)
        if len(calls)==2:
            # Valid schema and quote, but belongs to an earlier input batch.
            return draft_for(calls[0])
        return draft_for(chunks)
    monkeypatch.setattr(deepseek,'extract_candidates',output)
    result=client.post(base+'/extract',params={'strategy':'batched','plan_sha256':plan['plan_sha256']}).json()
    assert result['task']['status']=='failed'
    assert result['task']['error']['code']=='EXTRACTION_EVIDENCE_INVALID'
    assert len(calls)==2
    assert db_session.scalar(select(func.count()).select_from(CandidateKnowledge).where(CandidateKnowledge.project_id==uuid.UUID(project)))==0


def test_split_chunk_promotion_preserves_later_occurrence_line(client,db_session,configured,monkeypatch):
    monkeypatch.setattr(routes,'get_settings',lambda:configured.model_copy(update={'extraction_max_input_chars':1500}))
    project,source=prepared(client,'# Repeat\n\n'+('Repeated source fact.\n'*130))
    monkeypatch.setattr(deepseek,'extract_candidates',lambda _settings,chunks:draft_for(chunks))
    base=f"/api/v1/sources/{source['source_id']}";plan=client.get(base+'/extraction-plan').json()
    response=client.post(base+'/extract',params={'strategy':'batched','plan_sha256':plan['plan_sha256']})
    assert response.json()['task']['status']=='succeeded',response.text
    candidates=client.get(f'/api/v1/projects/{project}/reviews').json()['items']
    assert len(candidates)>1
    later=max(candidates,key=lambda item:item['evidence'][0]['start_line'])
    assert later['evidence'][0]['start_line']>3
    original=db_session.get(SourceChunk,uuid.UUID(later['evidence'][0]['chunk_id']))
    assert original.source_id==uuid.UUID(source['source_id'])
    resolved=client.post(f"/api/v1/reviews/{later['id']}/resolve",json={'action':'confirm'})
    assert resolved.status_code==200,resolved.text
    evidence=db_session.scalars(select(KnowledgeEvidence).where(KnowledgeEvidence.project_id==uuid.UUID(project))).one()
    assert evidence.start_line==later['evidence'][0]['start_line']


def test_batch_budget_refuses_large_inputs_before_provider(client,configured,monkeypatch):
    monkeypatch.setattr(routes,'get_settings',lambda:configured.model_copy(update={'extraction_max_input_chars':1000}))
    project,source=prepared(client,'x'*10000)
    monkeypatch.setattr(deepseek,'extract_candidates',lambda *_:pytest.fail('Unexpected provider call'))
    response=client.get(f"/api/v1/sources/{source['source_id']}/extraction-plan")
    assert response.status_code==413
    assert response.json()['error']['code']=='EXTRACTION_BATCH_LIMIT'
