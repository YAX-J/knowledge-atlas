"""Offline M5 packet validation, zero-call preflight, acceptance and reported-run scoring.

This CLI cannot execute providers, approve proposals, migrate business data or publish.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Literal
import xml.etree.ElementTree as ET

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from app.schemas.knowledge import StrictModel

ROOT=Path(__file__).resolve().parents[2]
PACKET=ROOT/'evaluation/development/project-agent-m5-v1'
PACKET_SHA256='1b7759bc8acb503b6541ea4711c6ca0ccec8f4fdd757782090fc62efa9e42d9b'
CATEGORIES={'evidence','organization','code','notes','governance'}
FILES={'fixture.json','cases.json','rubric.json','acceptance.json'}

class PacketError(ValueError):pass

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def read_json(path):
    raw=Path(path).read_bytes()
    if len(raw)>4_000_000:raise PacketError('JSON input exceeds 4 MB')
    return json.loads(raw)

def write_json(path,value):
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    temporary.replace(path)

def validate_packet(directory=PACKET):
    directory=Path(directory).resolve()
    seal=read_json(directory/'seal.json')
    if (set(seal)!={'protocol','files','packet_sha256'} or seal.get('protocol')!='project-agent-seal-v1'
        or set(seal.get('files',{}))!=FILES):
        raise PacketError('Invalid packet seal/files')
    hashes={name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in sorted(FILES)}
    if hashes!=seal['files'] or digest(hashes)!=seal.get('packet_sha256') or digest(hashes)!=PACKET_SHA256:
        raise PacketError('Frozen packet checksum mismatch; create a new packet version')
    packet=read_json(directory/'cases.json');fixture=read_json(directory/'fixture.json')
    rubric=read_json(directory/'rubric.json');matrix=read_json(directory/'acceptance.json')
    cases=packet['cases'];materials={m['id']:m for m in fixture['materials']}
    knowledge={k['id']:k for k in fixture['confirmed_knowledge']}
    if packet['phase']!='development' or len(cases)!=20 or len({c['id'] for c in cases})!=20:
        raise PacketError('Expected exactly 20 unique development cases')
    if Counter(c['category'] for c in cases)!=Counter({c:4 for c in CATEGORIES}):
        raise PacketError('Expected four cases per category')
    if not fixture['fictional'] or len(materials)!=len(fixture['materials']):raise PacketError('Invalid fictional material identities')
    for case in cases:
        scope=case['scope'];ids=scope['sources']+scope['note_revisions']
        if set(ids)-materials.keys() or set(scope['knowledge'])-knowledge.keys():raise PacketError('Unknown fixture scope')
        if any(materials[i]['kind']!='source' for i in scope['sources']) or any(materials[i]['kind']!='note' for i in scope['note_revisions']):
            raise PacketError('Mixed material kinds')
        if scope['valid_at'] and (ids or case['allowed_actions']):raise PacketError('Historical case mixes raw attachments/actions')
        if scope.get('knowledge_valid_to_overrides'):
            if set(scope['knowledge_valid_to_overrides'])-set(scope['knowledge']):raise PacketError('Out-of-scope knowledge override')
        if not case['expected']['facts'] or not case['expected']['invariants']:raise PacketError('Missing observable expectations')
        if case['limits']!=dict(model=8,tool=16,embedding=0,seconds=230):raise PacketError('Unexpected task budget')
        for anchor in case['expected']['citation_anchors']:
            content=materials[anchor['material']]['content'].splitlines()
            if not 1<=anchor['start_line']<=anchor['end_line']<=len(content):raise PacketError('Invalid exact citation anchor')
    checks=matrix['checks']
    if len({c['id'] for c in checks})!=len(checks):raise PacketError('Duplicate acceptance check')
    for check in checks:
        path,function=check['test'].split('::')
        if not re.fullmatch(r'tests/test_[a-z0-9_]+\.py',path) or not re.fullmatch(r'test_[a-z0-9_]+',function):
            raise PacketError('Unsafe acceptance test path')
        tree=ast.parse((ROOT/'backend'/path).read_text(encoding='utf-8'))
        if not any(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==function for n in tree.body):
            raise PacketError('Acceptance test no longer exists')
    return dict(packet=packet,fixture=fixture,rubric=rubric,matrix=matrix,packet_sha256=PACKET_SHA256)

def implementation_fingerprint():
    paths=[]
    for folder in ['backend/app','backend/migrations/versions','frontend/src']:
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in {'.py','.ts','.vue','.css'})
    paths.extend(ROOT/p for p in ['backend/pyproject.toml','frontend/package.json','frontend/package-lock.json',
        'backend/scripts/project_agent_m5.py','backend/scripts/m5_offline.py'])
    return digest({p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in sorted(paths)})

def fresh_output(directory):
    directory=Path(directory).resolve();allowed=(ROOT/'output').resolve()
    if directory==allowed or not directory.is_relative_to(allowed):raise PacketError('Output must be a fresh child of repository/output')
    directory.mkdir(parents=True,exist_ok=False)
    return directory

def preflight(data,*,model,endpoint,task_ids=None):
    if not model.strip() or len(model)>255:raise PacketError('Invalid configured model identifier')
    selected=[c['id'] for c in data['packet']['cases']] if task_ids is None else task_ids
    known={c['id'] for c in data['packet']['cases']}
    if not selected or len(set(selected))!=len(selected) or set(selected)-known:raise PacketError('Invalid/duplicate task selection')
    return dict(protocol='project-agent-preflight-v1',packet_id=data['packet']['packet_id'],packet_sha256=PACKET_SHA256,
        implementation_sha256=implementation_fingerprint(),schema_revision=data['packet']['schema_revision'],
        selected_task_ids=selected,provider_adapter='existing_deepseek_adapter',model=model,
        endpoint_sha256=hashlib.sha256(endpoint.rstrip('/').encode()).hexdigest(),
        runtime_protocol='assistant-task-v3',report_protocol='assistant-report-v2',
        per_task=dict(model=8,tool=16,embedding=0,seconds=230),
        maximum_attempts=dict(model=8*len(selected),tool=16*len(selected),embedding=0,judge=0),
        reserved=dict(model=0,embedding=0,judge=0),completed=dict(model=0,embedding=0,judge=0),
        github_transport='local_snapshot_substitute_only',github_network_requests=0,
        operator_approval='explicit per-operation human decisions; no automatic approval or resume',
        authorization=None,live_execution_allowed=False,live_executor_available=False,cost_estimate=None,
        human_grading_coverage=0,provider_model_snapshot_verified=False,
        pending=['separate provider/model/budget authorization','live run executor and isolated fixture replay',
            'operator review for write cases','task-specific independent semantic grades','fresh final-quality set after debugging',
            'hosted CI and release authorization'])

class Observation(StrictModel):
    case_id:str=Field(pattern=r'^[EPCNG]0[1-4]$')
    task:dict|None=None
    failure_code:str|None=Field(default=None,max_length=100)
    elapsed_ms:int=Field(ge=0,strict=True)
    material_ids:dict[str,str]=Field(default_factory=dict)
    safety_findings:list[str]=Field(default_factory=list,max_length=30)

class ReportedRun(StrictModel):
    protocol:Literal['project-agent-reported-run-v1']
    packet_sha256:str
    preflight_sha256:str
    source_mode:Literal['substitute','externally_reported_live']
    observations:list[Observation]=Field(max_length=20)

class Grade(StrictModel):
    case_id:str
    observation_sha256:str
    reviewer_id:str=Field(min_length=1,max_length=100)
    reviewer_kind:Literal['human','model']
    complete:bool=Field(strict=True)
    factuality:int=Field(ge=0,le=4,strict=True)
    completeness:int=Field(ge=0,le=4,strict=True)
    citation_support:int=Field(ge=0,le=4,strict=True)
    uncertainty:Literal['low','medium','high']
    rationale:str=Field(min_length=1,max_length=2000)

class BoundVersion(StrictModel):
    id:str
    sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    note_id:str|None=None

class ExportScope(BaseModel):
    model_config=ConfigDict(extra='ignore')
    source_ids:list[str]
    source_versions:list[BoundVersion]
    note_versions:list[BoundVersion]=Field(default_factory=list)
    allowed_actions:list[str]=Field(default_factory=list)
    valid_at:AwareDatetime|None=None

def _allowed_materials(case,data):
    allowed=set(case['scope']['sources']+case['scope']['note_revisions'])
    records={k['id']:k for k in data['fixture']['confirmed_knowledge']}
    allowed|={records[i]['source'] for i in case['scope']['knowledge']}
    if case['scope'].get('repository'):allowed.update(data['fixture']['repository']['files'])
    return allowed

def mechanical_checks(observation,case,data):
    from app.schemas.assistant import AssistantRead
    errors=[];task=None
    if observation.task is None:return dict(structurally_valid=False,errors=['no_task_export'],status='unavailable',usage=None)
    try:task=AssistantRead.model_validate(observation.task)
    except ValidationError:return dict(structurally_valid=False,errors=['invalid_task_export'],status='invalid',usage=None)
    try:task.scope=ExportScope.model_validate(task.scope).model_dump(mode='json')
    except ValidationError:return dict(structurally_valid=False,errors=['invalid_task_scope'],status=task.status,usage=task.usage)
    if task.execution_mode!='async_v3' or task.goal!=case['goal']:errors.append('task_protocol_or_goal_mismatch')
    materials={m['id']:m for m in data['fixture']['materials']};allowed=_allowed_materials(case,data)
    bindings=observation.material_ids
    if set(bindings)-allowed or len(set(bindings.values()))!=len(bindings):errors.append('material_bindings_invalid')
    required=set(case['scope']['sources']+case['scope']['note_revisions'])
    if required-bindings.keys():errors.append('missing_material_bindings')
    if set(task.scope.get('source_ids',[]))!={bindings.get(i) for i in case['scope']['sources']}:errors.append('source_scope_mismatch')
    if set(task.scope.get('allowed_actions',[]))!=set(case['allowed_actions']):errors.append('capability_scope_mismatch')
    if {r.get('id') for r in task.scope.get('note_versions',[])}!={bindings.get(i) for i in case['scope']['note_revisions']}:errors.append('note_scope_mismatch')
    try:
        def stamp(value):return datetime.fromisoformat(value).astimezone(timezone.utc) if value else None
        if stamp(task.scope.get('valid_at'))!=stamp(case['scope']['valid_at']):errors.append('knowledge_time_mismatch')
    except (ValueError,TypeError):errors.append('knowledge_time_mismatch')
    def material_hash(m):
        content=m['content'] if m['kind']=='source' else m['title']+'\n'+m['content']
        return hashlib.sha256(content.encode()).hexdigest()
    for group,key in [('source_versions','sources'),('note_versions','note_revisions')]:
        versions={r.get('id'):r.get('sha256') for r in task.scope.get(group,[])}
        for identifier in case['scope'][key]:
            if versions.get(bindings.get(identifier))!=material_hash(materials[identifier]):errors.append('scope_hash_mismatch')
    for kind in ('model','tool','embedding'):
        used=task.usage.get(kind)
        if type(used) is not int or not 0<=used<=case['limits'][kind]:errors.append('invalid_or_exceeded_budget')
    reverse={value:key for key,value in bindings.items()}
    if task.status=='succeeded' and task.result is None:errors.append('missing_result')
    if task.result:
        result=task.result
        if (result.protocol!='assistant-report-v2' or result.action=='finish' and result.report is None
            or result.action=='ask_user' and not result.question):errors.append('invalid_result_shape')
        identifiers=[r.id for r in result.references]
        required_refs={i for claim in result.report.claims for i in claim.reference_ids} if result.report else set()
        if len(identifiers)!=len(set(identifiers)) or required_refs-set(identifiers):errors.append('invalid_result_references')
    for ref in task.result.references if task.result else []:
        identifier=reverse.get(str(ref.revision_id if ref.kind=='note' else ref.source_id))
        if identifier not in allowed:errors.append('reference_out_of_scope');continue
        material=materials[identifier];lines=material['content'].splitlines()
        excerpt='\n'.join(lines[ref.start_line-1:ref.end_line])
        if (ref.end_line>len(lines) or ref.source_sha256!=material_hash(material)
            or ref.quote.rstrip('\n') not in excerpt):errors.append('reference_provenance_mismatch')
    return dict(structurally_valid=not errors,errors=sorted(set(errors)),status=task.status,usage=task.usage)

def assess(data,flight,run_data,grade_data=None):
    if (flight.get('protocol')!='project-agent-preflight-v1' or flight.get('packet_sha256')!=PACKET_SHA256
        or flight.get('live_execution_allowed') is not False):raise PacketError('Invalid zero-call preflight')
    selected=flight['selected_task_ids'];cases={c['id']:c for c in data['packet']['cases']}
    if len(set(selected))!=len(selected) or set(selected)-cases.keys():raise PacketError('Invalid preflight task selection')
    if (flight.get('per_task')!=dict(model=8,tool=16,embedding=0,seconds=230)
        or flight.get('maximum_attempts')!=dict(model=8*len(selected),tool=16*len(selected),embedding=0,judge=0)
        or flight.get('authorization') is not None or flight.get('live_executor_available') is not False
        or flight.get('reserved')!=dict(model=0,embedding=0,judge=0)
        or flight.get('completed')!=dict(model=0,embedding=0,judge=0)):raise PacketError('Preflight policy changed')
    run=ReportedRun.model_validate(run_data)
    if run.packet_sha256!=PACKET_SHA256 or run.preflight_sha256!=digest(flight):raise PacketError('Run packet/preflight binding mismatch')
    rows={r.case_id:r for r in run.observations}
    if len(rows)!=len(run.observations) or set(rows)-set(selected):raise PacketError('Duplicate/out-of-plan observation')
    hashes={id:digest(r.model_dump(mode='json')) for id,r in rows.items()}
    mechanical={id:mechanical_checks(r,cases[id],data) for id,r in rows.items()}
    grades=[];seen=set()
    if grade_data is not None:
        if (grade_data.get('protocol')!='project-agent-task-grades-v1' or grade_data.get('packet_sha256')!=PACKET_SHA256
            or grade_data.get('reported_run_sha256')!=digest(run_data)):raise PacketError('Grade packet/run binding mismatch')
        for raw in grade_data.get('grades',[]):
            grade=Grade.model_validate(raw);key=(grade.case_id,grade.reviewer_kind)
            if grade.case_id not in rows or grade.observation_sha256!=hashes[grade.case_id] or key in seen:raise PacketError('Duplicate or unbound grade')
            if not mechanical[grade.case_id]['structurally_valid']:raise PacketError('Cannot grade an invalid task export')
            if grade.complete and mechanical[grade.case_id]['status']!='succeeded':raise PacketError('Unfinished execution cannot be graded complete')
            seen.add(key);grades.append(grade)
    attempted=len(rows);structural=sum(r['structurally_valid'] for r in mechanical.values())
    safety=sum(len(r.safety_findings) for r in rows.values())
    by_reviewer={}
    for kind in ('human','model'):
        subset=[g for g in grades if g.reviewer_kind==kind];n=len(subset);passed=sum(g.complete for g in subset)
        means={d:sum(getattr(g,d) for g in subset)/n if n else None for d in data['rubric']['dimensions']}
        thresholds=data['rubric']['predeclared_thresholds']
        threshold_met=(passed/attempted>=thresholds['task_completion_rate_min']
            and all(v>=thresholds['semantic_dimension_mean_min'] for v in means.values())
            and means['citation_support']>=thresholds['citation_support_mean_min']
            and safety==0 and structural==attempted) if attempted and n==attempted else None
        by_reviewer[kind]=dict(graded=n,coverage=n/attempted if attempted else 0,
            task_completion_rate=passed/attempted if attempted and n==attempted else None,
            confirmed_completion_lower_bound=passed/attempted if attempted and n else None,
            completion_among_graded=passed/n if n else None,
            semantic_means=means,selected_plan_threshold_met=threshold_met,
            full_packet_threshold_met=threshold_met if attempted==20 else None,
            high_uncertainty=sum(g.uncertainty=='high' for g in subset))
    # Only measured fields are reported. A preparation/scoring command never certifies a release.
    return dict(protocol='project-agent-task-summary-v1',packet_sha256=PACKET_SHA256,reported_run_sha256=digest(run_data),
        source_mode=run.source_mode,source_provider_provenance_verified=False,planned=len(selected),attempted=attempted,
        full_packet_observed=attempted==20,
        not_attempted=[i for i in selected if i not in rows],structurally_valid=structural,
        structural_failure_rate=(attempted-structural)/attempted if attempted else None,
        server_succeeded=sum(r['status']=='succeeded' for r in mechanical.values()),
        safety_findings_reported=safety,records=[dict(case_id=i,observation_sha256=hashes[i],elapsed_ms=rows[i].elapsed_ms,
            safety_findings=rows[i].safety_findings,**mechanical[i]) for i in selected if i in rows],
        grades=by_reviewer,quality_measured=bool(grades),release_status='not_certified',
        thresholds=data['rubric']['predeclared_thresholds'],live_requests_this_command=0,
        limitations=['server success is not semantic completion','external grades and provider provenance are reported, not independently verified',
            'development set cannot serve as fresh final quality evidence','approval/recovery correctness requires engineering evidence, not an answer judge'])

def review_template(data,flight,run_data):
    summary=assess(data,flight,run_data)
    cases={c['id']:c for c in data['packet']['cases']}
    return dict(protocol='project-agent-task-grades-v1',packet_sha256=PACKET_SHA256,reported_run_sha256=digest(run_data),grades=[],
        instruction='Keep ungraded rows here. Put only explicitly completed human/model grades in grades; null is never zero.',
        ungraded=[dict(case_id=r['case_id'],observation_sha256=r['observation_sha256'],reviewable=r['structurally_valid'],
            structural_errors=r['errors'],expected=cases[r['case_id']]['expected'],reviewer_id=None,reviewer_kind=None,
            complete=None,factuality=None,completeness=None,citation_support=None,uncertainty=None,rationale=None) for r in summary['records']])

def acceptance(data,output,*,full=False,native=False,frontend=False):
    files=sorted({c['test'].split('::')[0] for c in data['matrix']['checks']}|{'tests/test_m5_packet.py','tests/test_m5_flows.py'})
    commands=[('focused',ROOT/'backend',[sys.executable,'-m','pytest','-p','scripts.m5_offline',*files,'-o','addopts=',
        '-q','--tb=short','--show-capture=no',f'--basetemp={output/"focused-tmp"}',f'--junitxml={output/"focused.xml"}'])]
    if full:commands.append(('backend_full',ROOT/'backend',[sys.executable,'-m','pytest','-p','scripts.m5_offline',
        '--cov=app','--cov-fail-under=90',f'--cov-report=xml:{output/"backend-coverage.xml"}',
        f'--basetemp={output/"full-tmp"}','--tb=short','--show-capture=no',f'--junitxml={output/"backend.xml"}']))
    if native:commands.append(('native',ROOT/'backend',[sys.executable,'-m','scripts.verify_native']))
    if frontend:
        import shutil
        npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
        if not npm:raise PacketError('Existing npm is required; do not install dependencies automatically')
        commands.extend((name,ROOT/'frontend',[npm,'run',script]) for name,script in [('frontend_tests','test:coverage'),('frontend_build','build')])
    report=dict(protocol='project-agent-engineering-v1',packet_sha256=PACKET_SHA256,implementation_sha256=implementation_fingerprint(),
        evidence_kind='local_substitutes',live_provider_requests=0,hosted_ci='not_run',desktop='M34 recorded baseline; no UI change in M5',
        stages=[dict(name=n,command=c,cwd=str(w.relative_to(ROOT)),status='pending') for n,w,c in commands])
    env={**os.environ,'KA_M5_OFFLINE':'1'}
    env.pop('KA_GITHUB_ACCEPTANCE',None)
    write_json(output/'engineering.json',report)
    for stage,(_,cwd,command) in zip(report['stages'],commands):
        start=time.monotonic();stage['status']='running';write_json(output/'engineering.json',report)
        try:
            with (output/(stage['name']+'.log')).open('w',encoding='utf-8') as log:
                result=subprocess.run(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,check=False)
            stage.update(status='passed' if result.returncode==0 else 'failed',exit_code=result.returncode,
                elapsed_ms=round((time.monotonic()-start)*1000),log_sha256=hashlib.sha256((output/(stage['name']+'.log')).read_bytes()).hexdigest())
        except (OSError,KeyboardInterrupt):
            stage['status']='interrupted';write_json(output/'engineering.json',report);raise
        for name in ['focused','backend']:
            junit=output/(name+'.xml')
            if stage['name']=={'focused':'focused','backend':'backend_full'}[name] and junit.exists():
                suites=list(ET.parse(junit).getroot().iter('testsuite'))
                stage['tests']={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
        write_json(output/'engineering.json',report)
        print(f"{stage['name']}: {stage['status']}",flush=True)
        if stage['status']!='passed':return report
    return report

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['validate','preflight','acceptance','assess','review-template'])
    parser.add_argument('--packet',type=Path,default=PACKET)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--task',action='append',dest='tasks')
    parser.add_argument('--full',action='store_true');parser.add_argument('--native',action='store_true');parser.add_argument('--frontend',action='store_true')
    parser.add_argument('--preflight',type=Path);parser.add_argument('--reported-run',type=Path);parser.add_argument('--grades',type=Path)
    args=parser.parse_args(argv)
    try:
        data=validate_packet(args.packet)
        if args.action=='validate':
            print(json.dumps(dict(packet_sha256=PACKET_SHA256,cases=20,materials=len(data['fixture']['materials']),acceptance_checks=len(data['matrix']['checks']),live_requests=0)))
            return 0
        if args.output is None:raise PacketError('--output is required and must be fresh')
        if args.action=='preflight':
            from app.core.config import get_settings
            settings=get_settings()
            report=preflight(data,model=settings.deepseek_model,endpoint=settings.deepseek_base_url,task_ids=args.tasks)
        elif args.action in {'assess','review-template'}:
            if args.preflight is None or args.reported_run is None:raise PacketError('--preflight and --reported-run are required')
            flight=read_json(args.preflight);run=read_json(args.reported_run)
            report=review_template(data,flight,run) if args.action=='review-template' else assess(data,flight,run,read_json(args.grades) if args.grades else None)
        else:report=None
        output=fresh_output(args.output)
        if args.action=='acceptance':
            report=acceptance(data,output,full=args.full,native=args.native,frontend=args.frontend)
            return 0 if all(s['status']=='passed' for s in report['stages']) else 1
        write_json(output/({'preflight':'preflight.json','review-template':'review-template.json'}.get(args.action,'summary.json')),report)
        print(json.dumps(dict(action=args.action,output=str(output),live_requests=0)))
        return 0
    except (PacketError,ValidationError,ValueError,OSError,KeyError,TypeError) as exc:
        # Validation/connection details can include private input; emit only an error class.
        print(f'M5 command rejected ({type(exc).__name__}); inspect local inputs without exposing credentials.',file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
