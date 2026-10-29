import json
import uuid
from datetime import timedelta
import pytest
from sqlalchemy import func, select
from app.agents.registry import available_agents
from app.agents.runtime import RunContext, agent_scope, invoke_model, invoke_tool, run_scope
from app.api.routes import agents as routes
from app.core.errors import AppError
from app.models.agent_run import AgentRun
from app.models.domain import CandidateKnowledge, ProcessingTask, SourceDocument, utc_now
from app.models.graph import KnowledgeEntity
from app.services import deepseek
from tests.test_knowledge import configured, parsed_source
from tests.test_questions import prepared_project
from tests.test_sources import create_project


def tool(name,args,identifier='call-1'):
    return {'tool_calls':[dict(id=identifier,type='function',function=dict(name=name,arguments=json.dumps(args)))]}


def prepare(client,monkeypatch,settings):
    project,source,draft=parsed_source(client)
    monkeypatch.setattr(routes,'get_settings',lambda:settings)
    seen=[]
    def turn(_settings,messages,tools,**kwargs):
        seen.append(messages)
        if messages[-1]['role']=='user':
            ids=json.loads(messages[-1]['content'])['chunks']
            return tool('read_chunk',{'chunk_id':ids[-1]['chunk_id']})
        assert 'PostgreSQL' in messages[-1]['content']
        return {'content':json.dumps(draft)}
    monkeypatch.setattr(deepseek,'call_agent_turn',turn)
    return project,source,draft,seen


def test_registry_and_global_budget_count_failed_attempts_and_isolate_roles():
    assert set(available_agents())=={'code_analysis','knowledge_extraction','evidence_qa'}
    context=RunContext(user_id=uuid.uuid4(),project_id=uuid.uuid4(),model_limit=2,tool_limit=1)
    with run_scope(context):
        with agent_scope('code_analysis'):
            with pytest.raises(ValueError):invoke_model(lambda:(_ for _ in ()).throw(ValueError('private data')))
        with agent_scope('knowledge_extraction'):
            assert invoke_model(lambda:3)==3
            with pytest.raises(AppError):invoke_model(lambda:pytest.fail('Must not call provider'))
            assert invoke_tool(lambda:{'ok':True})=={'ok':True}
            with pytest.raises(AppError):invoke_tool(lambda:pytest.fail('Must not execute tool'))
        with pytest.raises(AppError):
            with run_scope(RunContext(user_id=context.user_id,project_id=uuid.uuid4())):pass
    assert context.counts==dict(model=2,tool=1,embedding=0)
    assert 'private data' not in json.dumps(context.events)


def test_knowledge_pipeline_pauses_for_real_human_review_and_resumes_without_providers(client,db_session,configured,monkeypatch):
    project,source,draft,seen=prepare(client,monkeypatch,configured)
    url=f'/api/v1/projects/{project}/agent-runs'
    body=dict(request_id=str(uuid.uuid4()),kind='knowledge_pipeline',source_id=source['source_id'])
    response=client.post(url,json=body)
    assert response.status_code==200,response.text
    data=response.json()
    assert data['status']=='awaiting_review' and data['review_counts']=={'pending':3}
    assert client.get(f"/api/v1/sources/{source['source_id']}/extraction").json()['candidate_count']==3
    assert data['usage']['model']==2 and data['usage']['tool']==1
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEntity).where(KnowledgeEntity.project_id==uuid.UUID(project)))==0
    assert client.post(url,json=body).json()==data and len(seen)==2
    path=url+'/'+data['id']
    assert client.get(path).json()['result']['candidate_ids']==data['result']['candidate_ids']
    assert client.post(path+'/resume').status_code==409
    review=client.post(f'/api/v1/projects/{project}/reviews/resolve-batch',json=dict(source_id=source['source_id'],
        review_ids=data['result']['candidate_ids'],action='confirm'))
    assert review.status_code==200,review.text
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_args,**_kw:pytest.fail('Resume must be free'))
    done=client.post(path+'/resume')
    assert done.status_code==200 and done.json()['status']=='succeeded'
    assert done.json()['review_counts']=={'confirmed':3} and done.json()['usage']==data['usage']
    assert client.post(path+'/resume').json()==done.json()
    assert client.get(url).json()['total']==1
    changed=client.post(url,json={**body,'model_limit':1})
    assert changed.status_code==409


def test_budget_failure_releases_extraction_lease_and_never_autoretries(client,db_session,configured,monkeypatch):
    project,source,_draft,seen=prepare(client,monkeypatch,configured)
    url=f'/api/v1/projects/{project}/agent-runs'
    body=dict(request_id=str(uuid.uuid4()),kind='knowledge_pipeline',source_id=source['source_id'],model_limit=0)
    data=client.post(url,json=body).json()
    assert data['status']=='failed' and data['error_code']=='AGENT_BUDGET_EXCEEDED' and not seen
    task=db_session.scalar(select(ProcessingTask).where(ProcessingTask.type=='knowledge_candidates',ProcessingTask.source_id==uuid.UUID(source['source_id'])))
    assert task.status=='failed' and task.execution_id is None
    assert db_session.scalar(select(func.count()).select_from(CandidateKnowledge).where(CandidateKnowledge.project_id==uuid.UUID(project)))==0
    assert client.post(url,json=body).json()==data and not seen
    assert client.post(url+'/'+data['id']+'/resume').status_code==409


def test_workflow_scope_source_time_and_unknown_request_boundaries(client,db_session,configured,monkeypatch):
    project,source,_draft,_seen=prepare(client,monkeypatch,configured)
    other=create_project(client)
    base=f'/api/v1/projects/{other}/agent-runs'
    body=dict(request_id=str(uuid.uuid4()),kind='knowledge_pipeline',source_id=source['source_id'])
    assert client.post(base,json=body).status_code==404
    assert client.post(f'/api/v1/projects/{project}/agent-runs',json={**body,'valid_at':utc_now().isoformat()}).status_code==422
    assert client.post(f'/api/v1/projects/{project}/agent-runs',json={**body,'include_code_analysis':True}).status_code==422
    assert client.post(f'/api/v1/projects/{project}/agent-runs',json=dict(request_id=str(uuid.uuid4()),kind='question_pipeline',question='Example',include_code_analysis=True)).status_code==422
    assert client.get(base+'/'+body['request_id']).status_code==404
    data=client.post(f'/api/v1/projects/{project}/agent-runs',json=body).json()
    assert client.get(base+'/'+data['id']).status_code==404
    assert client.post(base+'/'+data['id']+'/resume').status_code==404
    record=db_session.get(AgentRun,uuid.UUID(data['id']))
    record.status='running';record.lease_until=utc_now()-timedelta(seconds=1)
    db_session.commit()
    read=client.get(f'/api/v1/projects/{project}/agent-runs/{record.id}')
    assert read.json()['status']=='interrupted'
    assert client.post(f'/api/v1/projects/{project}/agent-runs',json=body).json()['status']=='interrupted'


def test_question_agent_reads_tools_and_validates_final_citations(client,configured,monkeypatch):
    project,settings=prepared_project(client,monkeypatch)
    monkeypatch.setattr(routes,'get_settings',lambda:settings)
    calls=[]
    def answer(_settings,messages,tools,**kwargs):
        calls.append(messages)
        initial=json.loads(messages[1]['content'])['initial_evidence']
        if len(calls)==1:return tool('read_evidence',{'evidence_id':initial[0]['id']})
        return {'content':json.dumps(dict(supported=True,answer='PostgreSQL stores knowledge.',confidence=.9,
            citation_ids=[initial[0]['id']],missing_information=[]))}
    monkeypatch.setattr(deepseek,'call_agent_turn',answer)
    body=dict(request_id=str(uuid.uuid4()),kind='question_pipeline',question='PostgreSQL',retrieval_mode='bm25')
    result=client.post(f'/api/v1/projects/{project}/agent-runs',json=body)
    assert result.status_code==200,result.text
    data=result.json();assert data['status']=='succeeded' and data['result']['answer']['supported']
    assert data['usage']['model']==2 and len(calls)==2
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_args,**_kwargs:{'content':json.dumps(dict(
        supported=True,answer='Invented evidence',confidence=.9,citation_ids=[str(uuid.uuid4())],missing_information=[]))})
    bad=client.post(f'/api/v1/projects/{project}/agent-runs',json={**body,'request_id':str(uuid.uuid4())}).json()
    assert bad['status']=='failed' and bad['error_code']=='QUESTION_EVIDENCE_INVALID'


def test_empty_question_workflow_refuses_without_models(client,configured,monkeypatch):
    project=create_project(client);monkeypatch.setattr(routes,'get_settings',lambda:configured)
    monkeypatch.setattr(deepseek,'call_agent_turn',lambda *_a,**_k:pytest.fail('No evidence must be free'))
    result=client.post(f'/api/v1/projects/{project}/agent-runs',json=dict(request_id=str(uuid.uuid4()),kind='question_pipeline',question='Unknown'))
    assert result.status_code==200,result.text
    data=result.json()
    assert data['status']=='succeeded' and not data['result']['answer']['supported'] and data['usage']['model']==0


def test_code_and_extraction_share_budget_and_pass_validated_findings(client,configured,monkeypatch):
    from tests.test_code_agent import _code,_repository
    from app.schemas.code_agent import AgentCallAnalysisDraft
    project=create_project(client);repository=_repository(client,project)
    _code(client,project,repository,'helper.ts','export function save() {return 1;}\n')
    main=_code(client,project,repository,'main.ts','import {save} from "./helper";\nsave();\n')
    chunks=client.get(f"/api/v1/sources/{main['source_id']}/chunks").json()['items']
    quote=next(item for item in chunks if 'save();' in item['content'])
    monkeypatch.setattr(routes,'get_settings',lambda:configured)
    def analyze(_settings,payload):
        call=payload['calls'][0]
        return AgentCallAnalysisDraft.model_validate({'decisions':[dict(call_id=call['id'],target_ids=[call['candidates'][0]['id']],
            resolution='resolved',confidence=.9,resolution_basis='Exact import and declaration')]})
    monkeypatch.setattr(deepseek,'analyze_cross_file_calls',analyze)
    findings=[]
    def turn(_settings,messages,tools,**kwargs):
        if messages[-1]['role']=='user':
            data=json.loads(messages[-1]['content']);findings.append(data['code_findings'])
            return tool('read_chunk',{'chunk_id':quote['id']})
        return {'content':json.dumps(dict(entities=[dict(local_id='call',type='CodeEntity',name='Save call',summary='Calls save',
            confidence=.9,evidence=[dict(chunk_id=quote['id'],quote='save();')])],relations=[]))}
    monkeypatch.setattr(deepseek,'call_agent_turn',turn)
    url=f'/api/v1/projects/{project}/agent-runs'
    body=dict(request_id=str(uuid.uuid4()),kind='knowledge_pipeline',source_id=main['source_id'],include_code_analysis=True,model_limit=2)
    failed=client.post(url,json=body).json()
    assert failed['status']=='failed' and failed['usage']['model']==2 and failed['error_code']=='AGENT_BUDGET_EXCEEDED'
    success=client.post(url,json={**body,'request_id':str(uuid.uuid4()),'model_limit':8}).json()
    assert success['status']=='awaiting_review' and success['usage']['model']==3
    assert findings[-1]['calls'][0]['callee']=='save'
    assert {event['agent'] for event in success['events']}=={'workflow','code_analysis','knowledge_extraction'}
    assert any(event.get('tool_name')=='read_chunk' for event in success['events'])
