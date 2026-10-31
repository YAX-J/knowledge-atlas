"""Frozen independent packet, zero-call preflight and honest reported-run denominators."""
import hashlib
import json
import shutil
import subprocess
import uuid
import pytest
from app.core.config import Settings
from scripts import project_agent_m5 as m5

@pytest.fixture
def packet():return m5.validate_packet()

def flight(packet,ids=None):return m5.preflight(packet,model='local-model-placeholder',endpoint='https://example.invalid',task_ids=ids)

def observed(packet,case_id='E01',status='succeeded',**changes):
    case=next(c for c in packet['packet']['cases'] if c['id']==case_id)
    materials={m['id']:m for m in packet['fixture']['materials']}
    ids={name:str(uuid.uuid4()) for name in case['scope']['sources']+case['scope']['note_revisions']}
    task=dict(id=str(uuid.uuid4()),project_id=str(uuid.uuid4()),goal=case['goal'],status=status,error_code=None,
        created_at='2026-10-31T00:00:00Z',updated_at='2026-10-31T00:00:00Z',execution_mode='async_v3',
        scope=dict(source_ids=[ids[i] for i in case['scope']['sources']],allowed_actions=case['allowed_actions'],
            valid_at=case['scope']['valid_at'],source_versions=[dict(id=ids[i],sha256=hashlib.sha256(materials[i]['content'].encode()).hexdigest()) for i in case['scope']['sources']],
            note_versions=[dict(id=ids[i],sha256=hashlib.sha256((materials[i]['title']+'\n'+materials[i]['content']).encode()).hexdigest()) for i in case['scope']['note_revisions']]),
        result=dict(protocol='assistant-report-v2',action='finish',report=dict(title='Synthetic test',claims=[dict(text='Placeholder for structural unit testing only.',status='uncertain',reference_ids=[])],missing_information=['No semantic grade exists.'])) if status=='succeeded' else None,events=[],usage=dict(model=2,tool=1,embedding=0))
    return dict(case_id=case_id,task=task,elapsed_ms=100,material_ids=ids,safety_findings=[])|changes

def reported(packet,fl,rows):return dict(protocol='project-agent-reported-run-v1',packet_sha256=m5.PACKET_SHA256,preflight_sha256=m5.digest(fl),source_mode='substitute',observations=rows)
def grades(packet,run,rows):return dict(protocol='project-agent-task-grades-v1',packet_sha256=m5.PACKET_SHA256,reported_run_sha256=m5.digest(run),grades=rows)
def grade(row,**changes):
    normalized=m5.Observation.model_validate(row).model_dump(mode='json')
    return dict(case_id=row['case_id'],observation_sha256=m5.digest(normalized),reviewer_id='synthetic-test-reviewer',reviewer_kind='model',complete=True,
        factuality=4,completeness=4,citation_support=4,uncertainty='low',rationale='Synthetic unit grade only, not an evaluation result.')|changes

def test_packet_balanced_independent_and_exact_anchors(packet):
    assert len(packet['packet']['cases'])==20 and len(packet['fixture']['materials'])==11
    assert packet['packet']['base_commit']=='e0998c4'
    assert {c['category'] for c in packet['packet']['cases']}==m5.CATEGORIES
    assert len(packet['matrix']['checks'])==18
    text=json.dumps(packet['fixture'],ensure_ascii=False)
    assert 'Cinder Relay' in text and 'Nimbus' not in text and 'holdout-v3' not in text
    historical=next(c for c in packet['packet']['cases'] if c['id']=='E03')
    assert historical['scope']['valid_at'] and not historical['scope']['sources']
    assert next(c for c in packet['packet']['cases'] if c['id']=='G02')['scope']['knowledge_valid_to_overrides']=={'retention-old':None}

@pytest.mark.parametrize('name',['fixture.json','cases.json','rubric.json','acceptance.json','seal.json'])
def test_packet_tampering_rejected_even_if_local_seal_is_rewritten(tmp_path,name):
    target=tmp_path/'packet';shutil.copytree(m5.PACKET,target)
    data=json.loads((target/name).read_text(encoding='utf-8'));data['tampered']=True
    (target/name).write_text(json.dumps(data),encoding='utf-8')
    if name!='seal.json':
        seal=json.loads((target/'seal.json').read_text());seal['files'][name]=hashlib.sha256((target/name).read_bytes()).hexdigest();seal['packet_sha256']=m5.digest(seal['files'])
        (target/'seal.json').write_text(json.dumps(seal))
    with pytest.raises(m5.PacketError):m5.validate_packet(target)

def test_preflight_reads_no_providers_and_reserves_nothing(packet,monkeypatch):
    import httpx
    monkeypatch.setattr(httpx.Client,'send',lambda *_a,**_k:pytest.fail('No network in preflight'))
    before={p:p.read_bytes() for p in m5.PACKET.iterdir() if p.is_file()}
    result=flight(packet)
    assert result['maximum_attempts']==dict(model=160,tool=320,embedding=0,judge=0)
    assert result['reserved']==result['completed']==dict(model=0,embedding=0,judge=0)
    assert result['authorization'] is None and not result['live_execution_allowed'] and not result['live_executor_available']
    assert result['cost_estimate'] is None and not result['provider_model_snapshot_verified']
    assert result['github_network_requests']==0 and result['human_grading_coverage']==0
    assert all(p.read_bytes()==content for p,content in before.items())
    assert flight(packet,['N04','E02'])['maximum_attempts']['model']==16

@pytest.mark.parametrize('ids',[[],['E01','E01'],['unknown']])
def test_invalid_task_selection_rejected(packet,ids):
    with pytest.raises(m5.PacketError):flight(packet,ids)

def test_success_is_not_completion_and_failures_stay_in_denominator(packet):
    fl=flight(packet);rows=[observed(packet),observed(packet,'E02',status='failed'),observed(packet,'P04',status='waiting_approval'),dict(case_id='C01',task=None,failure_code='UNKNOWN_RESPONSE',elapsed_ms=200)]
    run=reported(packet,fl,rows);result=m5.assess(packet,fl,run)
    assert result['planned']==20 and result['attempted']==4 and len(result['not_attempted'])==16
    assert result['server_succeeded']==1 and result['structurally_valid']==3 and result['structural_failure_rate']==.25
    assert result['grades']['human']['coverage']==result['grades']['model']['coverage']==0
    assert result['grades']['model']['task_completion_rate'] is None and not result['quality_measured']
    partial=m5.assess(packet,fl,run,grades(packet,run,[grade(rows[0])]))
    assert partial['grades']['model']['coverage']==.25 and partial['grades']['model']['task_completion_rate'] is None
    assert partial['grades']['model']['confirmed_completion_lower_bound']==.25
    assert partial['grades']['model']['completion_among_graded']==1
    assert partial['grades']['human']['coverage']==0 and partial['release_status']=='not_certified'

def test_grades_bound_to_exact_records_and_safety_overrides_threshold(packet):
    fl=flight(packet,['E01']);row=observed(packet,safety_findings=['operator-reported unauthorized write'])
    run=reported(packet,fl,[row]);result=m5.assess(packet,fl,run,grades(packet,run,[grade(row)]))
    assert result['grades']['model']['task_completion_rate']==1 and result['grades']['model']['selected_plan_threshold_met'] is False
    clean=observed(packet);run=reported(packet,fl,[clean]);result=m5.assess(packet,fl,run,grades(packet,run,[grade(clean)]))
    assert result['grades']['model']['selected_plan_threshold_met'] is True and result['grades']['model']['full_packet_threshold_met'] is None
    assert result['release_status']=='not_certified' and result['source_provider_provenance_verified'] is False

@pytest.mark.parametrize('mutation',['duplicate','foreign','wrong_run','wrong_record','invalid_export','invented_score'])
def test_grade_and_record_tampering_rejected(packet,mutation):
    fl=flight(packet,['E01']);row=observed(packet);run=reported(packet,fl,[row]);evaluation=grades(packet,run,[grade(row)])
    if mutation=='duplicate':evaluation['grades'].append(grade(row))
    if mutation=='foreign':evaluation['grades'][0]['case_id']='E02'
    if mutation=='wrong_run':evaluation['reported_run_sha256']='0'*64
    if mutation=='wrong_record':evaluation['grades'][0]['observation_sha256']='0'*64
    if mutation=='invalid_export':
        row['task']['goal']='wrong';run=reported(packet,fl,[row]);evaluation=grades(packet,run,[grade(row)])
    if mutation=='invented_score':evaluation['grades'][0]['factuality']=5
    with pytest.raises(ValueError):m5.assess(packet,fl,run,evaluation)

def test_duplicate_unknown_cases_and_preflight_mismatch(packet):
    fl=flight(packet,['E01']);row=observed(packet)
    for run in [reported(packet,fl,[row,row]),reported(packet,fl,[observed(packet,'E02')]),reported(packet,fl,[row])|{'preflight_sha256':'0'*64}]:
        with pytest.raises(m5.PacketError):m5.assess(packet,fl,run)
    result=m5.assess(packet,fl,reported(packet,fl,[]))
    assert result['attempted']==0 and result['structural_failure_rate'] is None and result['not_attempted']==['E01']

@pytest.mark.parametrize('mutation',['scope','hash','budget','time','extra_binding','invalid_shape'])
def test_mechanical_failures_do_not_disappear_from_attempts(packet,mutation):
    fl=flight(packet,['E01']);row=observed(packet)
    if mutation=='scope':row['task']['scope']['source_ids']=[]
    if mutation=='hash':row['task']['scope']['source_versions'][0]['sha256']='0'*64
    if mutation=='budget':row['task']['usage']['model']=True
    if mutation=='time':row['task']['scope']['valid_at']='2024-06-01T00:00:00Z'
    if mutation=='extra_binding':row['material_ids']['note-r3']=str(uuid.uuid4())
    if mutation=='invalid_shape':row['task']['unexpected']='not a task field'
    result=m5.assess(packet,fl,reported(packet,fl,[row]))
    assert result['attempted']==1 and result['structurally_valid']==0 and result['structural_failure_rate']==1

def test_fresh_output_is_confined_and_never_overwrites(tmp_path):
    with pytest.raises(m5.PacketError):m5.fresh_output(m5.ROOT/'backend'/'not-an-output-directory')
    target=m5.ROOT/'output'/('m5-output-unit-'+uuid.uuid4().hex)
    assert m5.fresh_output(target)==target
    with pytest.raises(FileExistsError):m5.fresh_output(target)
    target.rmdir()

def test_acceptance_fail_stop_saves_commands_and_transport_barrier(packet,tmp_path,monkeypatch):
    called=[]
    def run(command,**kwargs):
        called.append(command);assert kwargs['env']['KA_M5_OFFLINE']=='1' and 'KA_GITHUB_ACCEPTANCE' not in kwargs['env']
        return subprocess.CompletedProcess(command,1)
    monkeypatch.setattr(subprocess,'run',run)
    report=m5.acceptance(packet,tmp_path,full=True,native=True)
    assert len(called)==1 and '-p' in called[0] and 'scripts.m5_offline' in called[0]
    assert [s['status'] for s in report['stages']]==['failed','pending','pending']
    assert json.loads((tmp_path/'engineering.json').read_text())==report

def test_cli_preflight_and_overwrite_refusal(packet,monkeypatch,capsys):
    monkeypatch.setattr('app.core.config.get_settings',lambda:Settings(_env_file=None,deepseek_api_key='private-fixture-only'))
    output=m5.ROOT/'output'/('m5-preflight-unit-'+uuid.uuid4().hex)
    try:
        assert m5.main(['validate'])==0
        assert m5.main(['preflight','--output',str(output),'--task','E01'])==0
        report=json.loads((output/'preflight.json').read_text());assert report['maximum_attempts']['model']==8
        assert 'private-fixture-only' not in json.dumps(report)
        original=(output/'preflight.json').read_bytes()
        assert m5.main(['preflight','--output',str(output)])==1
        assert (output/'preflight.json').read_bytes()==original
        assert m5.main(['preflight','--output',str(output.parent/'unused'),'--task','bad'])==1
        assert 'private-fixture-only' not in capsys.readouterr().out
    finally:
        if output.exists():
            for path in output.iterdir():path.unlink()
            output.rmdir()

@pytest.mark.parametrize('change',[{'maximum_attempts':{}},{'authorization':{'approved':True}},{'reserved':{'model':1,'embedding':0,'judge':0}},{'live_execution_allowed':True}])
def test_modified_preflight_policy_is_never_accepted_as_a_grant(packet,change):
    fl=flight(packet,['E01'])|change
    with pytest.raises(m5.PacketError):m5.assess(packet,fl,reported(packet,fl,[]))

def test_review_template_keeps_null_grades_and_does_not_invent_measurements(packet):
    fl=flight(packet,['E01']);run=reported(packet,fl,[observed(packet)])
    template=m5.review_template(packet,fl,run)
    assert template['grades']==[] and template['ungraded'][0]['complete'] is None
    assert template['ungraded'][0]['factuality'] is None and template['ungraded'][0]['reviewer_kind'] is None
    summary=m5.assess(packet,fl,run,template)
    assert not summary['quality_measured'] and summary['grades']['human']['coverage']==0

def test_nested_scope_shapes_are_structural_failures_instead_of_crashes(packet):
    fl=flight(packet,['E01']);row=observed(packet);row['task']['scope']['source_versions']='not an array'
    summary=m5.assess(packet,fl,reported(packet,fl,[row]))
    assert summary['attempted']==1 and summary['structurally_valid']==0
    assert summary['records'][0]['errors']==['invalid_task_scope']

def test_exact_reference_provenance_and_missing_report_references(packet):
    fl=flight(packet,['E01']);row=observed(packet);material=packet['fixture']['materials'][0]
    identifier=str(uuid.uuid4());ref=dict(id=identifier,kind='source',source_id=row['material_ids']['overview'],
        source_sha256=hashlib.sha256(material['content'].encode()).hexdigest(),path=material['path'],start_line=5,end_line=5,
        quote=material['content'].splitlines()[4])
    row['task']['result']['references']=[ref]
    row['task']['result']['report']['claims']=[dict(text='A quoted engineering fixture.',status='referenced',reference_ids=[identifier])]
    assert m5.assess(packet,fl,reported(packet,fl,[row]))['structurally_valid']==1
    ref['quote']='Invented quote'
    assert 'reference_provenance_mismatch' in m5.assess(packet,fl,reported(packet,fl,[row]))['records'][0]['errors']
    row['task']['result']['references']=[]
    assert 'invalid_result_references' in m5.assess(packet,fl,reported(packet,fl,[row]))['records'][0]['errors']

@pytest.mark.parametrize('status',['failed','interrupted','waiting_approval','cancelled','queued','running'])
def test_unfinished_execution_cannot_be_imported_as_completed(packet,status):
    fl=flight(packet,['E01']);row=observed(packet,status=status);run=reported(packet,fl,[row])
    with pytest.raises(m5.PacketError):m5.assess(packet,fl,run,grades(packet,run,[grade(row)]))
