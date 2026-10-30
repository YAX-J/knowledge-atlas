import json
from pathlib import Path

import httpx
from pydantic import SecretStr
import pytest

from app.core.config import Settings
from app.llm.providers import jev
from scripts import jev_evaluation as runner
from scripts.evaluate_dataset import validate_dataset


def settings(**changes):
    return Settings(_env_file=None,typesafe_api_key=SecretStr('test-jev-key'),**changes)


def response(questions,model='jev-1.14.0'):
    answers={}
    for name,question in questions.items():
        options=list(question['criteria'])
        choice='supported' if 'supported' in options else options[0]
        answers[name]=dict(type='choice',choice=choice,confidence=.9,
            probabilities={option:1. if option==choice else 0. for option in options})
    return dict(model=model,answers=answers,usage=dict(input_tokens=50,output_tokens=0))


def packet(tmp_path):
    root=tmp_path/'packet';root.mkdir()
    rows=[dict(review_id='review-0001',question='Storage?',answer='Uses a database.',supported=True,
        reference_answer='Uses a database.',required_facts=['database'],answerable=True,granularity='claim',
        units=[dict(claim='Uses a database.',passages=[dict(quote='Uses a database.',context='Uses a database.')])])]
    runner.write(root/'packet.json',rows)
    runner.write(root/'packet-manifest.json',dict(protocol=jev.PROTOCOL,packet_sha256=runner.digest(rows)))
    return root


@pytest.mark.parametrize('mode',['success','foreign_model','unknown_choice','bad_sum','missing_answer','nan','usage','usage_null','401','timeout','oversized'])
def test_jev_transport_is_bounded_strict_and_never_retries(monkeypatch,mode):
    calls=[]
    questions={'relation':dict(type='choice',instructions='Judge support',criteria=runner.RELATION)}
    def handler(request):
        calls.append(request)
        if mode=='timeout':raise httpx.ReadTimeout('test-jev-key private text',request=request)
        if mode=='401':return httpx.Response(401,text='test-jev-key private text')
        if mode=='oversized':return httpx.Response(200,content=b'x'*(128*1024+1))
        value=response(questions)
        answer=value['answers']['relation']
        if mode=='foreign_model':value['model']='jev-latest'
        if mode=='unknown_choice':answer['choice']='invented'
        if mode=='bad_sum':answer['probabilities']={key:.5 for key in runner.RELATION}
        if mode=='missing_answer':value['answers']={}
        if mode=='nan':answer['confidence']=float('nan')
        if mode=='usage':value['usage']['input_tokens']=-1
        if mode=='usage_null':value['usage']=None
        return httpx.Response(200,content=json.dumps(value).encode())
    original=httpx.Client
    monkeypatch.setattr(jev.httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    if mode=='success':
        result=jev.judge(settings(),{'claim':'Fact','passages':[]},questions)
        assert result['answers']['relation']['choice']=='supported'
    else:
        with pytest.raises(jev.JevError) as error:jev.judge(settings(),{},questions)
        assert 'test-jev-key' not in str(error.value) and 'private' not in str(error.value)
    assert len(calls)==1 and calls[0].url=='https://api.typesafe.ai/v1/systemone'


def test_dry_run_and_auth_budget_preflight_do_not_call_provider(tmp_path):
    root=packet(tmp_path)
    def forbidden(*_args):pytest.fail('Dry run cannot call a provider')
    result=runner.run(root,tmp_path/'dry',settings=Settings(_env_file=None),judge=forbidden)
    assert result['status']=='prepared' and result['planned_requests']==3
    assert result['reserved_requests']==result['completed_requests']==result['model_graded_reviews']==0
    assert result['human_grading_coverage']==0
    with pytest.raises(ValueError,match='BUDGET'):runner.run(root,tmp_path/'bad',allow_calls=True,max_requests=2,settings=settings(),judge=forbidden)
    with pytest.raises(ValueError,match='NOT_CONFIGURED'):runner.run(root,tmp_path/'auth',allow_calls=True,max_requests=3,settings=Settings(_env_file=None),judge=forbidden)
    with pytest.raises(jev.JevError,match='PINNED'):runner.run(root,tmp_path/'alias',settings=settings(typesafe_model='jev-latest'),judge=forbidden)
    with pytest.raises(jev.JevError,match='INPUT_TOO_LARGE'):jev.request_payload(settings(),{'text':'x'*25000},{})


def test_separate_reference_and_cited_evidence_with_order_check(tmp_path):
    root=packet(tmp_path);calls=[]
    def judge(config,state,questions):
        calls.append((state,questions))
        saved=json.loads((tmp_path/'graded'/'run.json').read_text(encoding='utf-8'))
        assert saved['reserved_requests']==len(calls)
        assert 'review_id' not in state and 'mode' not in state and 'confidence' not in state
        if 'relation' in questions:
            assert 'reference_answer' not in state and 'required_facts' not in state
        return response(questions)
    result=runner.run(root,tmp_path/'graded',settings=settings(),allow_calls=True,max_requests=3,judge=judge)
    assert result['status']=='succeeded' and result['model_graded_reviews']==1
    assert result['annotation_source']=='model' and result['human_grading_coverage']==0
    assert list(calls[1][1]['relation']['criteria'])==list(reversed(calls[2][1]['relation']['criteria']))
    assert result['reviews'][0]['uncertain_units']==[]
    with pytest.raises(FileExistsError):runner.run(root,tmp_path/'graded',settings=settings(),allow_calls=True,max_requests=3,judge=judge)


def test_failed_attempt_is_saved_without_retry_or_grades(tmp_path):
    root=packet(tmp_path);calls=[]
    def fail(*_args):calls.append(1);raise jev.JevError('JEV_PROVIDER_FAILED')
    with pytest.raises(jev.JevError):runner.run(root,tmp_path/'failed',settings=settings(),allow_calls=True,max_requests=3,judge=fail)
    saved=json.loads((tmp_path/'failed'/'run.json').read_text(encoding='utf-8'))
    assert saved['status']=='failed' and saved['reserved_requests']==len(calls)==1
    assert saved['completed_requests']==saved['model_graded_reviews']==0


def test_prepare_anonymizes_exports_and_verifies_frozen_quote(tmp_path):
    dataset=Path(__file__).resolve().parents[2]/'evaluation/public-v2'
    _,cases,_=validate_dataset(dataset)
    predictions=[dict(id=case['id'],answer=case['gold_answer'],supported=case['answerable'],
        citations=case['gold_evidence']) for case in cases]
    path=tmp_path/'mode-secret-name.jsonl'
    path.write_text(''.join(json.dumps(item)+'\n' for item in predictions),encoding='utf-8')
    rows=runner.prepare(dataset,[path],tmp_path/'prepared')
    assert len(rows)==len(cases) and all(set(row).isdisjoint({'mode','case_id','model'}) for row in rows)
    assert 'mode-secret-name' not in json.dumps(rows)
    assert all(row['granularity']=='legacy_answer' for row in rows)
    # These are synthetic test answers, not delivered evaluation grades.
    predictions[0]['citations'][0]['quote']='Fabricated test quote'
    path.write_text(''.join(json.dumps(item)+'\n' for item in predictions),encoding='utf-8')
    with pytest.raises(ValueError,match='QUOTE_INVALID'):runner.prepare(dataset,[path],tmp_path/'bad-quote')
