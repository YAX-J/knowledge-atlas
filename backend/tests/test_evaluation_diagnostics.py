import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.schemas.questions import ClaimAnswerDraft, ClaimAnswerDraftV2
from app.schemas.search import SearchRead
from app.services import deepseek
from scripts import evaluation_diagnostics as diagnostics
from scripts import run_public_acceptance as online
from tests.test_knowledge import configured
from tests.test_questions import prepared_project


ROOT = Path(__file__).resolve().parents[2]


def sample():
    evidence = dict(source='corpus/a.md', start_line=1, end_line=1, quote='fact')
    case = dict(id='case-1', category='direct_fact', question='Q', answerable=True,
                gold_answer='fact', required_facts=['fact'], gold_evidence=[evidence])
    prediction = dict(id='case-1', answer='partial answer', supported=False,
                      retrieved_evidence=[evidence], citations=[])
    quality = dict(correctness=dict(choice='incorrect', confidence=.7, probabilities=None),
                   completeness=dict(choice='partial', confidence=.9, probabilities=None),
                   abstention=dict(choice='appropriate', confidence=None, probabilities=None))
    return case, prediction, quality


def test_diagnostics_do_not_treat_uncertainty_or_missing_citations_as_retrieval_failure():
    case, prediction, quality = sample()
    support = [(dict(choice='supported', confidence=.9), dict(choice='supported', confidence=.79))]
    row = diagnostics.diagnose(case, prediction, quality, support)
    assert row['missing_from_pool'] == []
    assert 'retrieval_pool_gold_gap' not in row['flags']
    assert 'citation_gold_gap' in row['flags'] and 'model_flagged_incomplete' in row['flags']
    assert row['quality_low_confidence'] == ['correctness', 'abstention']
    assert row['citation_uncertain_units'] == [0] and row['human_grade'] is None


def test_diagnostics_distinguish_top5_and_full_pool_and_preserve_order_disagreement():
    case, prediction, quality = sample()
    prediction['retrieved_evidence'] = [dict(source='corpus/b.md', start_line=i, end_line=i, quote='other')
                                        for i in range(1, 6)] + case['gold_evidence']
    row = diagnostics.diagnose(case, prediction, quality,
        [(dict(choice='supported', confidence=.95), dict(choice='insufficient', confidence=.95))])
    assert row['missing_from_top5'] and not row['missing_from_pool']
    assert row['citation_uncertain_units'] == [0]


@pytest.mark.parametrize('mutation', ['none', 'packet_hash', 'mapping', 'prediction', 'duplicate', 'holdout', 'output_exists'])
def test_offline_analysis_checks_provenance_without_writing_inputs(tmp_path, monkeypatch, mutation):
    case, prediction, quality = sample()
    summary = dict(dataset_id='development')
    monkeypatch.setattr(diagnostics, 'validate_dataset', lambda _: ({}, [case], summary))
    dataset = tmp_path/'dataset'; dataset.mkdir()
    (dataset/'manifest.json').write_text('{}')
    (dataset/'cases.jsonl').write_text('{}')
    packet_dir = tmp_path/'packet'; packet_dir.mkdir()
    packet = [dict(review_id='review-1', question='Q', answer='partial answer', answerable=True,
                   reference_answer='fact', required_facts=['fact'], supported=False, units=[], granularity='legacy_answer')]
    manifest = dict(dataset=summary, packet_sha256=diagnostics.digest(packet))
    key = {'review-1': dict(prediction='bm25.jsonl', case_id='case-1')}
    run = dict(status='succeeded', human_grading_coverage=0, packet_sha256=manifest['packet_sha256'],
               judge_config={'model': 'test'}, judge_config_sha256=diagnostics.digest({'model': 'test'}),
               reserved_requests=1, results=[dict(review_id='review-1', part='quality', answers=quality)])
    if mutation == 'packet_hash': manifest['packet_sha256'] = 'changed'
    if mutation == 'mapping': key['review-1']['case_id'] = 'unknown'
    if mutation == 'prediction': prediction['answer'] = 'changed'
    if mutation == 'duplicate': run['results'] *= 2
    if mutation == 'holdout': summary['dataset_id'] = 'knowledge-atlas-holdout-v3'
    for name, value in [('packet.json', packet), ('packet-manifest.json', manifest), ('grading-key.json', key)]:
        (packet_dir/name).write_text(json.dumps(value))
    source_run = tmp_path/'run.json'; source_run.write_text(json.dumps(run))
    predictions = tmp_path/'bm25.jsonl'; predictions.write_text(json.dumps(prediction)+'\n')
    before = {path: path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()}
    target = tmp_path/'result'
    if mutation == 'output_exists': target.mkdir()
    if mutation != 'none':
        with pytest.raises(ValueError):
            diagnostics.analyze(dataset, [predictions], packet_dir, source_run, target)
    else:
        result = diagnostics.analyze(dataset, [predictions], packet_dir, source_run, target)
        assert result['rows'] == 1 and result['provider_requests_this_analysis'] == 0
        assert result['human_grading_coverage'] == 0
    assert all(path.read_bytes() == value for path, value in before.items())


@pytest.mark.parametrize('ledger_kind', ['present', 'missing', 'changed_limits'])
def test_holdout_preflight_reads_cumulative_budget_without_network_or_database(tmp_path, monkeypatch, ledger_kind):
    ledger = tmp_path/'ledger.json'
    if ledger_kind != 'missing':
        ledger.write_text(json.dumps(dict(limits=dict(model=120 if ledger_kind == 'present' else 999, embedding=160),
                                         reserved=dict(model=84, embedding=61))))
    before = ledger.read_bytes() if ledger.exists() else None
    if ledger_kind == 'changed_limits':
        with pytest.raises(ValueError, match='limits changed'):
            online.plan(ROOT/'evaluation/holdout-v3', settings=Settings(_env_file=None), ledger_path=ledger)
    else:
        result = online.plan(ROOT/'evaluation/holdout-v3', settings=Settings(_env_file=None), ledger_path=ledger)
        assert result['planned_upper_bounds']['model'] == 96
        assert result['planned_upper_bounds']['embedding'] >= 73
        assert result['blockers'] and result['reserved_requests'] == result['completed_requests'] == 0
        assert result['modes'] == ['bm25', 'vector', 'hybrid', 'rrf'] and not result['extraction_smoke']
        assert result['request_limits'] == dict(model=120,embedding=160)
        assert result['judge_protocol']['citation_confidence_threshold'] == .8
        assert result['historical_remaining'] == (dict(model=36, embedding=99) if before else None)
    assert (ledger.read_bytes() if ledger.exists() else None) == before


def test_live_run_refuses_insufficient_authorization_before_any_service(tmp_path, monkeypatch):
    monkeypatch.setattr(online, 'plan', lambda *_args, **_kwargs: {'blockers': ['budget']})
    monkeypatch.setattr(online, 'isolated_workspace', lambda *_: pytest.fail('Must not touch DB'))
    with pytest.raises(ValueError, match='cumulative authorization'):
        online.run(ROOT/'evaluation/holdout-v3', tmp_path/'live')
    assert not (tmp_path/'live').exists()


def test_online_export_uses_real_current_qa_claim_pool_and_historical_time(client, configured, db_session, monkeypatch):
    project, settings = prepared_project(client, monkeypatch)
    captured = []
    original = online.questions.search_knowledge
    def search(*args, **kwargs):
        captured.append(kwargs['valid_at'])
        return original(*args, **kwargs)
    monkeypatch.setattr(online.questions, 'search_knowledge', search)
    def answer(_settings, _question, evidence):
        return ClaimAnswerDraft(confidence=.8,
            claims=[dict(text='Evidence exists', status='supported', citation_ids=[evidence[0]['id']])], missing_information=[])
    monkeypatch.setattr(deepseek, 'answer_question', answer)
    from app.models.domain import SourceDocument
    from sqlalchemy import select
    sources = list(db_session.scalars(select(SourceDocument).where(SourceDocument.project_id == uuid.UUID(project))))
    mapping = {source.id: 'corpus/'+source.original_name for source in sources}
    case = dict(id='diagnostic', question='PostgreSQL', valid_at='2099-01-01T00:00:00Z')
    value = online.online_prediction(db_session, case=case, mode='bm25', project_id=uuid.UUID(project),
                                    settings=settings, mapping=mapping)
    assert captured[0].year == 2099
    assert value['answer_protocol'] == 'evidence-claims-v3' and value['claims']
    assert value['answer_correct'] is value['explainability_score'] is None
    assert value['answer_input_evidence'] and value['claim_evidence']
    pool = {item['id'] for item in value['answer_input_evidence']}
    assert all(str(identifier) in pool for claim in value['claims'] for identifier in claim['citation_ids'])
    assert value['retrieval_metadata']['lexical']['protocol'] == 'mixed-bm25-v2'


def test_incomplete_historical_vector_index_stops_before_answer_generation(monkeypatch):
    result = SearchRead(query='q', mode='vector', items=[], truncated=False, indexed_count=0, eligible_count=1)
    monkeypatch.setattr(online.questions, 'search_knowledge', lambda *_args, **_kwargs: result)
    with pytest.raises(ValueError, match='Incomplete vector index'):
        online.online_prediction(SimpleNamespace(), case=dict(id='x', question='q', valid_at=None),
            mode='vector', project_id=uuid.uuid4(), settings=Settings(_env_file=None), mapping={})


@pytest.mark.parametrize('approved', [None, 'changed'])
def test_holdout_requires_exact_approved_plan_before_services(tmp_path, monkeypatch, approved):
    value = dict(blockers=[], dataset=dict(dataset_id='knowledge-atlas-holdout-v3'))
    monkeypatch.setattr(online, 'plan', lambda *_args, **_kwargs: value)
    path = None
    if approved:
        path = tmp_path/'approved.json'; path.write_text('{}')
    with pytest.raises(ValueError, match='approved-plan|Approved plan changed'):
        online.run(ROOT/'evaluation/holdout-v3', tmp_path/'live', approved_plan=path)
    assert not (tmp_path/'live').exists()


@pytest.mark.parametrize('provider_failure', [False, True, 'output'])
@pytest.mark.parametrize('independent_round', [False, True])
def test_complete_holdout_runner_with_local_provider_substitutes_keeps_history_and_ledgers(db_session, tmp_path, monkeypatch, provider_failure, independent_round):
    """Exercise 96 current QA exports; local SQLite/stubs, never quality evidence."""
    settings = Settings(_env_file=None, deepseek_api_key=SecretStr('local-test'),
                        embedding_api_key=SecretStr('local-test'), embedding_model='test-1024',
                        embedding_base_url='https://local-substitute.invalid/v1')
    dataset = ROOT/'evaluation/holdout-v3'
    ledger = tmp_path/'ledger.json'
    ledger.write_text(json.dumps(dict(limits=dict(model=120, embedding=160),
        reserved=dict(model=0, embedding=0), attempts=[], authorization='unit fixture only')))
    original_plan = online.plan
    monkeypatch.setattr(online, 'get_settings', lambda: settings)
    monkeypatch.setattr(online, 'LEDGER_PATH', ledger)
    monkeypatch.setattr(online, 'plan', lambda path, **kwargs: original_plan(path, ledger_path=ledger, **kwargs))
    arguments = {}
    if independent_round:
        scope = original_plan(dataset,settings=settings,ledger_path=ledger)['authorization_scope']
        grant_path = tmp_path/'round.json'
        online.RoundLedger.create(grant_path,scope=scope,authorization=dict(
            id='unit-grant',source='test only',authorized_at='2026-10-31T00:00:00Z'))
        arguments = dict(authorization_ledger=grant_path,model_limit=96,embedding_limit=73)
        active_path = grant_path
    else:
        active_path = ledger
    if provider_failure=='output':
        arguments['isolate_output_errors']=True
    historical_before = ledger.read_bytes()
    approved = original_plan(dataset, settings=settings, ledger_path=ledger,**arguments)
    assert not approved['blockers']
    approved_path = tmp_path/'approved.json'; approved_path.write_text(json.dumps(approved))
    @contextmanager
    def workspace(_settings):
        yield db_session.get_bind(), settings, 'sqlite-unit-fixture'
    monkeypatch.setattr(online, 'isolated_workspace', workspace)
    calls = []
    def embedding(_settings, texts):
        assert json.loads(active_path.read_text())['reserved']['embedding'] > sum(c == 'embedding' for c in calls)
        calls.append('embedding')
        return [[1.0] + [0.0]*1023 for _ in texts]
    def answer(_settings, _question, evidence):
        online.model_usage.begin_call('question')
        calls.append('model')
        assert json.loads(active_path.read_text())['reserved']['model'] == sum(c == 'model' for c in calls)
        if provider_failure is True:
            raise RuntimeError('local substitute failure')
        if provider_failure=='output':
            raise deepseek.QuestionError('QUESTION_OUTPUT_INVALID','local substitute invalid output')
        return ClaimAnswerDraft(confidence=.8, claims=[dict(
            text='Local substitute only.', status='supported', citation_ids=[evidence[0]['id']])], missing_information=[])
    monkeypatch.setattr(online.embeddings, 'embed_texts', embedding)
    monkeypatch.setattr(deepseek, 'answer_question', answer)
    target = tmp_path/'run'
    if provider_failure is True:
        with pytest.raises(RuntimeError, match='local substitute failure'):
            online.run(dataset, target, approved_plan=approved_path,**arguments)
        failed = json.loads((target/'run.json').read_text())
        assert failed['status'] == 'failed' and failed['model_usage']['attempted'] == 1
        assert calls.count('model') == 1 and json.loads(active_path.read_text())['reserved']['model'] == 1
        if independent_round:
            assert ledger.read_bytes() == historical_before
        return
    result = online.run(dataset, target, approved_plan=approved_path,**arguments)
    assert result['status'] == ('completed_with_case_errors' if provider_failure=='output' else 'succeeded')
    assert result['human_coverage'] == 0
    assert result['embedding_calls'] == sum(c == 'embedding' for c in calls) <= 73
    assert result['model_usage']['attempted'] == sum(c == 'model' for c in calls) <= 96
    assert not (target/'extraction.json').exists()
    if independent_round:
        assert ledger.read_bytes() == historical_before
        assert original_plan(dataset,settings=settings,ledger_path=ledger,**arguments)['blockers']
    for mode in online.HOLDOUT_MODES:
        rows = [json.loads(line) for line in (target/f'{mode}.jsonl').read_text(encoding='utf-8').splitlines()]
        assert len(rows) == 24 and sum(row['valid_at'] is not None for row in rows) == 4
        assert all(row['answer_protocol'] == 'evidence-claims-v3' for row in rows)
        if provider_failure=='output':
            assert all(row.get('failure',{}).get('code')=='QUESTION_OUTPUT_INVALID' and row['answer'] is None for row in rows)
            assert result['modes'][mode]['answer_outcomes']==dict(total=24,invalid_output=24,available=0)
        else:
            assert all(row['claims'] is not None for row in rows)
        assert all(row['answer_correct'] is row['explainability_score'] is None for row in rows)
        projected = [json.loads(line) for line in (target/f'{mode}.metrics-input.jsonl').read_text(encoding='utf-8').splitlines()]
        assert [row['id'] for row in projected] == [row['id'] for row in rows]
        assert all('claims' not in row and 'answer_input_evidence' not in row for row in projected)


@pytest.mark.parametrize('failure', ['missing','scope','limit','tampered_counts','changed_grant','lock','spent','reuse'])
def test_round_ledger_rejects_missing_changed_exhausted_or_replayed_grants(tmp_path, failure):
    path=tmp_path/'grant.json'
    scope={'dataset':'unit'}
    if failure=='missing':
        with pytest.raises(FileNotFoundError): online.RoundLedger(path,scope=scope)
        return
    ledger=online.RoundLedger.create(path,scope=scope,authorization=dict(
        id='unit',source='test only',authorized_at='2026-10-31'))
    with pytest.raises(FileExistsError):
        online.RoundLedger.create(path,scope=scope,authorization={})
    if failure=='scope':
        with pytest.raises(ValueError): online.RoundLedger(path,scope={})
        return
    ledger.claim_run(tmp_path/'run')
    if failure=='reuse':
        with pytest.raises(RuntimeError,match='already claimed'): ledger.claim_run(tmp_path/'other')
        return
    if failure=='lock':
        ledger.lock.write_text('other writer')
        with pytest.raises(FileExistsError): ledger.reserve('answer')
        assert ledger.lock.exists()
        return
    data=json.loads(path.read_text())
    if failure=='limit': data['limits']['model']=97
    if failure=='tampered_counts': data['reserved']['model']=1
    if failure=='changed_grant': data['authorization']['id']='other'
    if failure=='spent':
        data['reserved']['model']=96
        data['attempts']=[dict(bucket='model',kind='answer',at='test') for _ in range(96)]
    path.write_text(json.dumps(data))
    with pytest.raises((ValueError,RuntimeError)):
        ledger.reserve('answer')
    assert not ledger.lock.exists()


def test_failure_classification_retains_validation_types_without_private_input_or_messages():
    try:
        ClaimAnswerDraft.model_validate(dict(supported='private-generated-text',confidence=.8,
            claims=[],missing_information=[]))
    except Exception as invalid:
        outer=RuntimeError('private-provider-message')
        outer.__cause__=invalid
        result=online.safe_failure_diagnostics(outer)
    assert result['exception_types']==['RuntimeError','ValidationError']
    assert result['validation_error_types']
    assert 'private-' not in json.dumps(result)


def test_safe_classification_identifies_static_constraint_without_response_values():
    try:
        ClaimAnswerDraftV2.model_validate(dict(supported=True,confidence=.8,claims=[dict(
            text='private-untrusted-answer',status='insufficient',citation_ids=[])],
            missing_information=['private-missing-detail']))
    except Exception as invalid:
        result=online.safe_failure_diagnostics(invalid)
    assert result['constraint_codes']==['overall_support_mismatch']
    assert 'private-' not in json.dumps(result)


@pytest.mark.parametrize('mutation',['none','input','citation','model','global_support','old_protocol'])
def test_explicit_diagnostic_reuse_requires_same_scope_and_exact_passages(client,configured,db_session,tmp_path,monkeypatch,mutation):
    from app.models.domain import SourceDocument
    from sqlalchemy import select
    project,settings=prepared_project(client,monkeypatch)
    project=uuid.UUID(project)
    sources=list(db_session.scalars(select(SourceDocument).where(SourceDocument.project_id==project)))
    mapping={source.id:'corpus/'+source.original_name for source in sources}
    def answer(_settings,_question,evidence):
        return ClaimAnswerDraft(confidence=.8,claims=[dict(
            text='Development fact.',status='supported',citation_ids=[evidence[0]['id']])],missing_information=[])
    monkeypatch.setattr(deepseek,'answer_question',answer)
    case=dict(id='development-case',question='PostgreSQL',valid_at=None)
    old=online.online_prediction(db_session,case=case,mode='bm25',project_id=project,settings=settings,mapping=mapping)
    current_ids=[item['id'] for item in old['answer_input_evidence']]
    remap={identifier:str(uuid.uuid4()) for identifier in current_ids}
    for field in ('answer_input_evidence','claim_evidence'):
        for item in old[field]: item['id']=remap[item['id']]
    for claim in old['claims']: claim['citation_ids']=[remap[item] for item in claim['citation_ids']]
    summary={'fingerprint_sha256':'development-fingerprint'}
    scope=dict(dataset_fingerprint_sha256=summary['fingerprint_sha256'],fixture_sha256='fixture',
        answer_model=settings.deepseek_model,answer_protocol='evidence-claims-v3',application_sha256=online.application_fingerprint())
    if mutation=='input': old['answer_input_evidence'][0]['quote']='different source content'
    if mutation=='citation': old['claims'][0]['citation_ids']=[str(uuid.uuid4())]
    if mutation=='model': scope['answer_model']='different-model'
    if mutation=='global_support': old['supported']=False
    if mutation=='old_protocol': scope['answer_protocol']='evidence-claims-v2'
    manifest=dict(protocol='verified-evaluation-answer-reuse-v1',scope=scope,prediction=old,
        source_run=dict(status='succeeded',reserved_model=1,case_id=case['id']))
    path=tmp_path/'reuse.json';path.write_text(json.dumps(manifest))
    monkeypatch.setattr(deepseek,'answer_question',lambda *_args,**_kwargs:pytest.fail('Reuse cannot call provider'))
    def perform():
        reused=online.load_reuse(path,summary,settings,'fixture')
        return online.reuse_prediction(db_session,case=case,project_id=project,settings=settings,mapping=mapping,reused=reused)
    if mutation=='none':
        reused=perform()
        assert reused['claims'][0]['citation_ids']==[current_ids[0]]
        assert reused['reuse']['latency_from_original_generation']
    else:
        with pytest.raises(ValueError): perform()
