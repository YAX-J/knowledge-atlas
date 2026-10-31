import json
import uuid

import httpx
import pytest
from pydantic import ValidationError

from app.schemas.questions import ClaimAnswerDraft
from app.services import deepseek
from tests.test_knowledge import configured
from tests.test_questions import prepared_project


def draft(citation=None):
    return dict(confidence=.8, claims=[dict(
        text='PostgreSQL stores knowledge.', status='supported', citation_ids=[str(citation or uuid.uuid4())])],
        missing_information=[])


@pytest.mark.parametrize('mutation', [
    'empty', 'too_many', 'missing_citation', 'insufficient_cited', 'duplicate', 'unknown_status',
    'overall_support', 'missing_information', 'long_text', 'flat_answer', 'extra_citations', 'nan',
])
def test_claim_schema_rejects_incomplete_or_inconsistent_support(mutation):
    value = draft()
    claim = value['claims'][0]
    if mutation == 'empty': value['claims'] = []
    if mutation == 'too_many': value['claims'] *= 9
    if mutation == 'missing_citation': claim['citation_ids'] = []
    if mutation == 'insufficient_cited': claim['status'] = 'insufficient'
    if mutation == 'duplicate': claim['citation_ids'] *= 2
    if mutation == 'unknown_status': claim['status'] = 'verified'
    if mutation == 'overall_support': value['supported'] = False
    if mutation == 'missing_information':
        claim.update(status='insufficient', citation_ids=[])
    if mutation == 'long_text': claim['text'] = 'x' * 501
    if mutation == 'flat_answer': value['answer'] = 'An unbound factual assertion.'
    if mutation == 'extra_citations':
        value['claims'] = [dict(text='Fact',status='supported',citation_ids=[str(uuid.uuid4())]) for _ in range(6)]
    if mutation == 'nan': value['confidence'] = float('nan')
    with pytest.raises(ValidationError):
        ClaimAnswerDraft.model_validate(value)


def test_claims_derive_flat_text_and_stable_unique_citation_union():
    a, b = uuid.uuid4(), uuid.uuid4()
    value = draft(a)
    value['claims'].append(dict(text='Second fact.',status='supported',citation_ids=[str(b),str(a)]))
    result = ClaimAnswerDraft.model_validate(value)
    assert result.citation_ids == [a, b]
    assert result.answer == 'PostgreSQL stores knowledge.\n\nSecond fact.'
    assert 'answer' not in result.model_dump() and 'citation_ids' not in result.model_dump()


def test_partial_claims_are_returned_with_exact_citation_mapping(client, configured, monkeypatch):
    project, _ = prepared_project(client, monkeypatch)
    def answer(_settings, _question, evidence):
        value = draft(evidence[0]['id'])
        value.update(missing_information=['No performance benchmark evidence.'])
        value['claims'].append(dict(text='Performance cannot be confirmed.',status='insufficient',citation_ids=[]))
        return ClaimAnswerDraft.model_validate(value)
    monkeypatch.setattr(deepseek,'answer_question',answer)
    response = client.post(f'/api/v1/projects/{project}/questions',json={'question':'PostgreSQL storage and performance?','retrieval_mode':'bm25'})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['answer_protocol'] == 'evidence-claims-v3' and not result['supported']
    assert result['claims'][0]['citation_ids'] == [result['evidence'][0]['id']]
    assert result['claims'][1]['citation_ids'] == []
    assert result['answer'] == '\n\n'.join(item['text'] for item in result['claims'])
    assert result['missing_information'] == ['No performance benchmark evidence.']


def test_claim_cannot_cite_evidence_from_another_project(client, configured, monkeypatch):
    first, _ = prepared_project(client, monkeypatch)
    seen = []
    def capture(_settings, _question, evidence):
        seen.append(evidence[0]['id'])
        return ClaimAnswerDraft.model_validate(draft(evidence[0]['id']))
    monkeypatch.setattr(deepseek,'answer_question',capture)
    assert client.post(f'/api/v1/projects/{first}/questions',json={'question':'PostgreSQL','retrieval_mode':'bm25'}).status_code == 200
    second, _ = prepared_project(client, monkeypatch)
    monkeypatch.setattr(deepseek,'answer_question',lambda *_: ClaimAnswerDraft.model_validate(draft(seen[0])))
    response = client.post(f'/api/v1/projects/{second}/questions',json={'question':'PostgreSQL','retrieval_mode':'bm25'})
    assert response.status_code == 502
    assert response.json()['error']['code'] == 'QUESTION_EVIDENCE_INVALID'


@pytest.mark.parametrize('legacy', [False, True])
def test_provider_requires_claims_without_flat_output_fallback(monkeypatch, configured, legacy):
    value = draft()
    if legacy:
        value.update(answer='Unbound answer',citation_ids=value.pop('claims')[0]['citation_ids'])
    original = httpx.Client
    def handler(request):
        prompt = json.loads(request.content)['messages'][0]['content']
        assert 'claims' in prompt and 'insufficient' in prompt
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]})
    monkeypatch.setattr(deepseek.httpx,'Client',lambda **kwargs: original(transport=httpx.MockTransport(handler),**kwargs))
    if legacy:
        with pytest.raises(deepseek.QuestionError) as exc:
            deepseek.answer_question(configured,'Question',[])
        assert exc.value.code == 'QUESTION_OUTPUT_INVALID'
    else:
        assert deepseek.answer_question(configured,'Question',[]).claims[0].text == value['claims'][0]['text']


@pytest.mark.parametrize('protocol', [None, 'evidence-claims-v2'])
def test_legacy_persisted_answer_remains_readable_without_new_provider_call(client, db_session, monkeypatch, protocol):
    from app.models.workspace import ConversationTurn
    project=client.post('/api/v1/projects',json={'name':'Legacy answer'}).json()['id']
    base=f'/api/v1/projects/{project}/conversations'
    conversation=client.post(base,json={}).json()['id']
    path=f'{base}/{conversation}/turns'
    body=dict(request_id=str(uuid.uuid4()),question='Known?',retrieval_mode='bm25')
    response=client.post(path,json=body)
    assert response.status_code == 200
    record=db_session.get(ConversationTurn,uuid.UUID(response.json()['id']))
    old=dict(record.answer)
    if protocol is None:
        old.pop('claims');old.pop('answer_protocol')
    else:
        old['answer_protocol'] = protocol
    record.answer=old
    db_session.commit()
    monkeypatch.setattr(deepseek,'answer_question',lambda *_a,**_k: pytest.fail('History cannot call provider'))
    history=client.get(path).json()['items'][0]['answer']
    assert history['answer'] == old['answer'] and history['supported'] == old['supported']
    assert history['claims'] == old.get('claims') and history['answer_protocol'] == protocol
    assert client.post(path,json=body).json()['answer'] == history
    db_session.refresh(record)
    assert record.answer == old


@pytest.mark.parametrize('legacy', [False, True])
def test_tool_workflow_rejects_missing_claim_citations_without_retry(client, configured, monkeypatch, legacy):
    from app.api.routes import agents as routes
    project, settings=prepared_project(client,monkeypatch)
    monkeypatch.setattr(routes,'get_settings',lambda:settings)
    calls=[]
    def answer(*_args,**_kwargs):
        calls.append(1)
        value=draft()
        value['claims'][0]['citation_ids']=[]
        if legacy:
            value.update(answer='Unbound prose',citation_ids=[str(uuid.uuid4())])
            value.pop('claims')
        return {'content':json.dumps(value)}
    monkeypatch.setattr(deepseek,'call_agent_turn',answer)
    body=dict(request_id=str(uuid.uuid4()),kind='question_pipeline',question='PostgreSQL',retrieval_mode='bm25')
    path=f'/api/v1/projects/{project}/agent-runs'
    response=client.post(path,json=body)
    assert response.status_code==200,response.text
    result=response.json()
    assert result['status']=='failed' and result['error_code']=='CALL_AGENT_OUTPUT_INVALID'
    assert not (result['result'] or {}).get('answer')
    assert result['usage']['model']==len(calls)==1
    assert client.post(path,json=body).json()['status']=='failed'
    assert len(calls)==1
