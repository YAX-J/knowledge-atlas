"""Run the new public corpus through the real online question service in an owned schema.

Explicit budgets, immutable corpus/index fingerprints, partial outputs and human
grades remaining empty are mandatory. No retry, private inputs or application writes.
"""
import argparse
import csv
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
import time
import uuid
from unittest.mock import patch
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.questions import AnswerClaim
from app.core.identity import DEVELOPMENT_USER_ID as USER
from app.llm.prompts import ANSWER_PROMPT_VERSION
from app.models.domain import CandidateKnowledge, Project
from app.services import embeddings, ingestion, knowledge, model_usage, parsing, questions
from app.services.search import search_knowledge
from scripts.evaluate_dataset import _evidence_key, score_predictions, validate_dataset
from scripts.evaluation_snapshot import project_snapshot
from scripts.isolated_workspace import isolated_workspace
from scripts.prepare_evaluation import load_fixture, prepare_project
from scripts.run_evaluation import _evidence_record, ordered_evidence, parse_valid_at
from scripts.provider_ledger import ProviderLedger, RoundLedger


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


LEDGER_PATH = Path(__file__).resolve().parents[2]/'output/completeness-20261026/provider-budget.json'
HOLDOUT_MODES = ['bm25', 'vector', 'hybrid', 'rrf']


def safe_failure_diagnostics(error):
    """Record error classes/counts only, never generated text, inputs or messages."""
    chain, counts, seen, constraints, fields = [], Counter(), set(), set(), set()
    known_constraints = {
        'Overall support must agree with claim support': 'overall_support_mismatch',
        'Insufficient claims must identify missing information': 'missing_insufficiency_reason',
        'Answer exceeds citation or text budget': 'answer_budget_exceeded',
        'Supported claims require citations; insufficient claims cannot cite': 'claim_citation_status_mismatch',
        'Claim citation IDs must be unique': 'duplicate_claim_citation',
    }
    known_fields = {'supported','confidence','claims','missing_information','text','status','citation_ids'}
    while error is not None and id(error) not in seen and len(chain) < 8:
        seen.add(id(error))
        chain.append(type(error).__name__)
        if isinstance(error, ValidationError):
            for item in error.errors(include_input=False,include_url=False):
                counts[item['type']] += 1
                fields.update(part for part in item['loc'] if isinstance(part,str) and part in known_fields)
                reason = str(item.get('ctx',{}).get('error',''))
                if reason in known_constraints:
                    constraints.add(known_constraints[reason])
        error = error.__cause__
    return dict(exception_types=chain, validation_error_types=dict(counts),
                schema_fields=sorted(fields),constraint_codes=sorted(constraints))


def application_fingerprint():
    root=Path(__file__).resolve().parents[1]
    return hashlib.sha256(json.dumps({path.relative_to(root).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((root/'app').rglob('*.py'))},sort_keys=True).encode()).hexdigest()


def load_reuse(path, summary, settings, fixture_hash):
    if path is None:
        return None
    raw=Path(path).read_bytes()
    value=json.loads(raw)
    expected=dict(dataset_fingerprint_sha256=summary['fingerprint_sha256'],fixture_sha256=fixture_hash,
        answer_model=settings.deepseek_model,answer_protocol=ANSWER_PROMPT_VERSION,
        application_sha256=application_fingerprint())
    if value['protocol']!='verified-evaluation-answer-reuse-v1' or value['scope']!=expected:
        raise ValueError('Diagnostic answer scope changed')
    prediction=value['prediction']
    source=value['source_run']
    if source['status']!='succeeded' or source['reserved_model']!=1 or source['case_id']!=prediction['id']:
        raise ValueError('Reuse requires one successful validated diagnostic answer')
    claims=[AnswerClaim.model_validate(item) for item in prediction['claims']]
    if (prediction.get('answer_protocol')!=ANSWER_PROMPT_VERSION or not claims or len(claims)>8
            or prediction.get('failure') or not isinstance(prediction['supported'],bool)
            or prediction['supported']!=all(item.status=='supported' for item in claims)
            or prediction['answer']!='\n\n'.join(item.text for item in claims)
            or prediction['answer_correct'] is not None or prediction['explainability_score'] is not None):
        raise ValueError('Invalid reusable claim export')
    value['file_sha256']=hashlib.sha256(raw).hexdigest()
    return value


def plan(dataset, *, settings=None, ledger_path=LEDGER_PATH, model_limit=120, embedding_limit=160,
         authorization_ledger=None,reuse_answer=None,isolate_output_errors=False):
    """Provider/DB-free plan; the historical authorization is never reset here."""
    settings = settings or get_settings()
    _, cases, summary = validate_dataset(dataset)
    protocol = json.loads((dataset/'protocol.json').read_text(encoding='utf-8'))
    if protocol['dataset'] != summary:
        raise ValueError('Frozen protocol fingerprint changed')
    if summary['dataset_id'] not in {'knowledge-atlas-public-v2', 'knowledge-atlas-holdout-v3'}:
        raise ValueError('Only frozen public-v2/holdout-v3 datasets are allowed')
    fixture, _, fixture_hash = load_fixture(dataset)
    reused=load_reuse(reuse_answer,summary,settings,fixture_hash)
    if reused and reused['prediction']['id'] not in {case['id'] for case in cases}:
        raise ValueError('Reusable case is outside this dataset')
    modes = HOLDOUT_MODES if summary['dataset_id'] == 'knowledge-atlas-holdout-v3' else protocol['modes']
    extraction = summary['dataset_id'] == 'knowledge-atlas-public-v2'
    entities = sum(len(source.entities) for source in fixture.sources)
    model_requests = len(cases) * sum(mode != 'keyword' for mode in modes) + (2 if extraction else 0)
    if reused:
        model_requests-=1
    embedding_requests = ((entities + settings.embedding_batch_size - 1) // settings.embedding_batch_size
                          + len(cases) * sum(mode in {'vector', 'hybrid', 'rrf'} for mode in modes))
    # A missing ledger is unknown authorization, not a fresh zero-use grant.
    ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else None
    remaining = {kind: ledger['limits'][kind] - ledger['reserved'][kind] for kind in ('model', 'embedding')} if ledger else None
    blockers = []
    if type(model_limit) is not int or type(embedding_limit) is not int or not 1 <= model_limit <= 120 or not 1 <= embedding_limit <= 160:
        raise ValueError('Budget exceeds the existing authorization')
    if ledger is None:
        blockers.append('Historical ledger missing; authorization must be reconciled before any call')
    elif ledger['limits'] != {'model': 120, 'embedding': 160}:
        raise ValueError('Historical authorization limits changed')
    scope = dict(dataset_id=summary['dataset_id'], dataset_fingerprint_sha256=summary['fingerprint_sha256'],
                 answer_model=settings.deepseek_model, embedding_model=settings.embedding_model,
                 embedding_dimensions=settings.embedding_dimensions, embedding_batch_size=settings.embedding_batch_size)
    if reused:
        scope['diagnostic_reuse_sha256']=reused['file_sha256']
    grant = None
    available = remaining
    if authorization_ledger is not None:
        if summary['dataset_id'] != 'knowledge-atlas-holdout-v3':
            raise ValueError('Independent round authorization is holdout-only')
        round_ledger = RoundLedger(authorization_ledger, scope=scope)
        grant = round_ledger.read()
        if model_limit > grant['limits']['model'] or embedding_limit > grant['limits']['embedding']:
            raise ValueError('Per-run caps exceed the new user authorization')
        available = {kind: grant['limits'][kind] - grant['reserved'][kind] for kind in ('model', 'embedding')}
        if grant['run_output'] is not None:
            blockers.append('Round already claimed; do not retry/resume in a fresh output')
    for kind, count, limit in (('model', model_requests, model_limit), ('embedding', embedding_requests, embedding_limit)):
        if count > limit or (available is not None and count > available[kind]):
            blockers.append(f'{kind}: planned upper bound {count} exceeds per-run or remaining cumulative budget')
    backend = Path(__file__).resolve().parents[1]
    code_files = [*sorted((backend/'app').rglob('*.py')), *(backend/'scripts'/name for name in (
        'run_public_acceptance.py', 'run_evaluation.py', 'evaluate_dataset.py', 'prepare_evaluation.py',
        'evaluation_snapshot.py', 'provider_ledger.py', 'isolated_workspace.py'))]
    code_hash = hashlib.sha256(json.dumps({path.relative_to(backend).as_posix():
        hashlib.sha256(path.read_bytes()).hexdigest() for path in code_files}, sort_keys=True).encode()).hexdigest()
    return dict(status='prepared', protocol='online-acceptance-plan-v1', dataset=summary,
                answer_protocol=ANSWER_PROMPT_VERSION, modes=modes, strategy='single_step',
                top_k_entities=5, max_answer_evidence=12, valid_at='each case.valid_at, never forced to current time',
                fixture_sha256=fixture_hash, dataset_protocol_sha256=hashlib.sha256((dataset/'protocol.json').read_bytes()).hexdigest(),
                embedding_batch_size=settings.embedding_batch_size, embedding_dimensions=settings.embedding_dimensions,
                answer_model=settings.deepseek_model, embedding_model=settings.embedding_model,
                code_sha256=code_hash,
                request_limits=dict(model=model_limit,embedding=embedding_limit),
                isolate_output_errors=isolate_output_errors,
                reuse_answer=(dict(case_id=reused['prediction']['id'],sha256=reused['file_sha256'],
                    mode='bm25',prior_model_attempts=1) if reused else None),
                planned_upper_bounds=dict(model=model_requests, embedding=embedding_requests),
                historical_remaining=remaining, blockers=blockers, extraction_smoke=extraction,
                authorization_scope=scope,
                round_authorization=(dict(id=grant['authorization']['id'], sha256=RoundLedger.identity(grant),
                    remaining=available, scope=scope) if grant is not None else None),
                human_coverage=0, reserved_requests=0, completed_requests=0,
                judge_protocol=dict(provider='cloudflare',model='@cf/cloudflare/clef',mode='decision',
                    citation_confidence_threshold=.8,model_revision_pinned=False),
                judge_requests='separate authorization after complete answer export; 1 + 2*cited supported claims per answer')


def online_prediction(db, *, case, mode, project_id, settings, mapping,isolate_output_errors=False):
    """Call the current application service once, preserving the actual prompt pool."""
    captured = {}
    original_search = questions.search_knowledge
    original_pool = questions.collect_answer_evidence

    def capture_search(*args, **kwargs):
        result = original_search(*args, **kwargs)
        if mode in {'vector', 'hybrid', 'rrf'} and result.indexed_count != result.eligible_count:
            raise ValueError('Incomplete vector index for requested historical scope')
        captured['result'] = result
        return result

    def capture_pool(*args, **kwargs):
        result = original_pool(*args, **kwargs)
        captured['pool'] = result[0]
        return result

    began = time.perf_counter()
    at = parse_valid_at(case['valid_at'])
    failure=None
    if mode == 'keyword':
        result = search_knowledge(db, user_id=USER, project_id=project_id, query=case['question'],
                                 types=[], valid_at=at, top_k=5, mode=mode, settings=settings)
        response = None
    else:
        with (patch.object(questions, 'search_knowledge', capture_search),
              patch.object(questions, 'collect_answer_evidence', capture_pool)):
            try:
                response = questions.answer_question(db, user_id=USER, project_id=project_id,
                    question=case['question'], valid_at=at, settings=settings, retrieval_mode=mode,
                    strategy='single_step')
            except AppError as exc:
                if not isolate_output_errors or exc.code!='QUESTION_OUTPUT_INVALID' or 'result' not in captured:
                    raise
                response=None
                failure=dict(code=exc.code,diagnostics=safe_failure_diagnostics(exc))
        result = captured['result']
        if response and (response.answer_protocol != ANSWER_PROMPT_VERSION or response.claims is None):
            raise ValueError('Current claim-level answer protocol is required')
    prediction = dict(id=case['id'], valid_at=case['valid_at'],
        retrieved_evidence=[_evidence_record(item, mapping) for item in ordered_evidence(result)],
        citations=[_evidence_record(item, mapping) for item in response.evidence] if response else [],
        answer=response.answer if response else None, supported=response.supported if response else None,
        latency_ms=round((time.perf_counter()-began)*1000, 3), answer_correct=None, explainability_score=None)
    if response or failure:
        pool = captured['pool']
        prediction.update(answer_protocol=ANSWER_PROMPT_VERSION,
            claims=[item.model_dump(mode='json') for item in response.claims] if response else None,
            claim_evidence=[dict(id=str(item.id), **_evidence_record(item, mapping)) for item in response.evidence] if response else [],
            answer_input_evidence=[dict(id=str(item.id), **_evidence_record(item, mapping)) for item in pool.values()],
            retrieval_metadata=result.model_dump(mode='json', exclude={'items'}))
    if failure:
        prediction['failure']=failure
    return prediction


def reuse_prediction(db, *, case, project_id, settings, mapping, reused):
    """Evaluation-only reuse after exact ordered evidence/version checks; no providers."""
    old=reused['prediction']
    if old['id']!=case['id'] or old['valid_at']!=case['valid_at']:
        raise ValueError('Reuse case/time mismatch')
    at=parse_valid_at(case['valid_at']) or datetime.now(timezone.utc)
    result=questions.search_knowledge(db,user_id=USER,project_id=project_id,query=case['question'],types=[],
        valid_at=at,top_k=5,mode='bm25',settings=settings)
    pool,_=questions.collect_answer_evidence(db,user_id=USER,project_id=project_id,at=at,result=result)
    records=[dict(id=str(item.id),**_evidence_record(item,mapping)) for item in pool.values()]
    def passage(item):
        return tuple(item[key] for key in ('source','start_line','end_line','quote'))
    if ([passage(item) for item in old['answer_input_evidence']]!=[passage(item) for item in records]
            or old['retrieved_evidence']!=[_evidence_record(item,mapping) for item in ordered_evidence(result)]):
        raise ValueError('Reusable answer input differs from current evidence')
    if len({passage(item) for item in records})!=len(records):
        raise ValueError('Ambiguous reused evidence identity')
    remap={before['id']:after['id'] for before,after in zip(old['answer_input_evidence'],records,strict=True)}
    claimed={item['id']:item for item in old['claim_evidence']}
    by_id={item['id']:item for item in records}
    value=json.loads(json.dumps(old))
    union=[]
    for claim in value['claims']:
        for identifier in claim['citation_ids']:
            if identifier not in remap or identifier not in claimed or passage(claimed[identifier])!=passage(by_id[remap[identifier]]):
                raise ValueError('Reusable citation is not bound to current exact passage')
        claim['citation_ids']=[remap[identifier] for identifier in claim['citation_ids']]
        union.extend(identifier for identifier in claim['citation_ids'] if identifier not in union)
    if len(union)>5 or len(value['answer'])>4000:
        raise ValueError('Reusable answer exceeds current budgets')
    value.update(claim_evidence=[by_id[identifier] for identifier in union],answer_input_evidence=records,
        citations=[{key:item[key] for key in ('source','start_line','end_line','quote')} for item in (by_id[i] for i in union)],
        retrieval_metadata=result.model_dump(mode='json',exclude={'items'}),
        reuse=dict(source_sha256=reused['file_sha256'],latency_from_original_generation=True))
    return value


def run(dataset,output,*,model_limit=120,embedding_limit=160,approved_plan=None,authorization_ledger=None,
        reuse_answer=None,isolate_output_errors=False):
    if output.exists():
        raise ValueError('Output directory must be new')
    settings=get_settings()
    prepared_plan=plan(dataset,settings=settings,model_limit=model_limit,embedding_limit=embedding_limit,
                       authorization_ledger=authorization_ledger,reuse_answer=reuse_answer,
                       isolate_output_errors=isolate_output_errors)
    if prepared_plan['blockers']:
        raise ValueError('Insufficient cumulative authorization; inspect --preflight before any provider call')
    if prepared_plan['dataset']['dataset_id'] == 'knowledge-atlas-holdout-v3' and approved_plan is None:
        raise ValueError('Holdout requires an explicit --approved-plan from the zero-call preflight')
    if approved_plan is not None and json.loads(Path(approved_plan).read_text(encoding='utf-8')) != prepared_plan:
        raise ValueError('Approved plan changed; repeat zero-call preflight and review before provider use')
    _,cases,summary=validate_dataset(dataset)
    if not settings.deepseek_api_key or not settings.embedding_api_key:
        raise ValueError('Providers are not configured')
    if not 1<=model_limit<=120 or not 1<=embedding_limit<=160:
        raise ValueError('Budget exceeds the user authorization')
    output.mkdir(parents=True)
    report=dict(status='running',protocol='online-claims-v4' if isolate_output_errors else 'online-claims-v3',prediction_protocol='online-claims-export-v1',
        answer_protocol=ANSWER_PROMPT_VERSION,dataset=summary,plan=prepared_plan,
        started_at=datetime.now(timezone.utc).isoformat(),private_inputs=False,human_coverage=0,
        planned_judge=prepared_plan['judge_protocol'],human_review_status='not_planned',
        billing_cost=None,embedding_calls=0,model_limit=model_limit,embedding_limit=embedding_limit,
        schema_removed=False,modes={},errors=[],case_failures=[],reused_answers=[])
    report_path=output/'run.json'
    save(report_path,report)
    original_embedding=embeddings.embed_texts
    original_begin=model_usage.begin_call
    ledger=(RoundLedger(authorization_ledger,scope=prepared_plan['round_authorization']['scope'])
            if authorization_ledger is not None else ProviderLedger(LEDGER_PATH))
    blind=[]
    predictions={}
    def measured_embedding(configuration,texts):
        if report['embedding_calls']>=embedding_limit:
            raise RuntimeError('Embedding budget exhausted')
        ledger.reserve('embedding')
        report['embedding_calls']+=1
        save(report_path,report)
        return original_embedding(configuration,texts)
    def measured_begin(kind):
        if len(meter.calls)>=model_limit:
            raise RuntimeError('Per-run model cap exhausted before ledger reservation')
        ledger.reserve(kind)
        original_begin(kind)
        report['model_usage']=meter.summary()
        save(report_path,report)
    try:
        if authorization_ledger is not None:
            ledger.claim_run(output)
        with model_usage.usage_budget(model_limit) as meter, patch.object(model_usage,'begin_call',measured_begin), patch.object(embeddings,'embed_texts',measured_embedding), isolated_workspace(settings) as (engine,native,schema):
            report['model_usage']=meter.summary()
            project_id=uuid.uuid4()
            prepared=prepare_project(engine=engine,dataset_root=dataset,project_id=project_id,settings=native,accept_curated_fixture=True)
            save(output/'preparation.json',prepared)
            mapping={uuid.UUID(value):path for path,value in prepared['source_ids'].items()}
            cached=None
            if reuse_answer is not None:
                reused=load_reuse(reuse_answer,summary,native,prepared_plan['fixture_sha256'])
                case=next(case for case in cases if case['id']==reused['prediction']['id'])
                with Session(engine) as db:
                    cached=reuse_prediction(db,case=case,project_id=project_id,settings=native,mapping=mapping,reused=reused)
                report['reused_answers'].append(prepared_plan['reuse_answer'])
            with Session(engine,expire_on_commit=False) as db:
                index=embeddings.rebuild_project_embeddings(db,user_id=USER,project_id=project_id,settings=native)
            report['index']=index
            with Session(engine) as db:
                frozen=project_snapshot(db,user_id=USER,project_id=project_id)
            report['snapshot']=frozen
            for mode in prepared_plan['modes']:
                records=[]
                partial=output/f'{mode}.partial.jsonl'
                for case in cases:
                    report['current_case']=dict(mode=mode,case_id=case['id'])
                    save(report_path,report)
                    with Session(engine) as db:
                        if cached is not None and mode=='bm25' and case['id']==cached['id']:
                            prediction=cached
                        else:
                            prediction=online_prediction(db,case=case,mode=mode,project_id=project_id,settings=native,
                                mapping=mapping,isolate_output_errors=isolate_output_errors)
                    if prediction.get('failure'):
                        report['case_failures'].append(dict(mode=mode,case_id=case['id'],**prediction['failure']))
                    records.append(prediction)
                    with partial.open('a',encoding='utf-8') as file:
                        file.write(json.dumps(prediction,ensure_ascii=False)+'\n')
                    if mode!='keyword' and prediction['answer'] is not None:
                        blind.append(dict(mode=mode,case=case,prediction=prediction))
                    report['model_usage']=meter.summary()
                    save(report_path,report)
                    print(f"{mode} {case['id']}: saved; model={len(meter.calls)}, embedding={report['embedding_calls']}",flush=True)
                # Keep the frozen line-evidence-v2 scorer/schema unchanged. The
                # richer claim export is for judging; numeric metrics use its
                # explicit legacy-field projection, also saved for reproduction.
                fields=('id','retrieved_evidence','citations','answer','supported','latency_ms',
                        'answer_correct','explainability_score')
                scoring_records=[{key:record[key] for key in fields} for record in records]
                metrics=score_predictions(cases=cases,predictions=scoring_records)
                metrics['answer_outcomes']=dict(total=len(records),invalid_output=sum(bool(r.get('failure')) for r in records),
                    available=sum(r['answer'] is not None for r in records))
                (output/f'{mode}.metrics-input.jsonl').write_text(''.join(
                    json.dumps(record,ensure_ascii=False)+'\n' for record in scoring_records),encoding='utf-8')
                save(output/f'{mode}.metrics.json',metrics)
                partial.rename(output/f'{mode}.jsonl')
                report['modes'][mode]=metrics
                predictions[mode]=records
                with Session(engine) as db:
                    if project_snapshot(db,user_id=USER,project_id=project_id)!=frozen:
                        raise RuntimeError('Knowledge/index changed during evaluation')
                save(report_path,report)
            # Independent extraction smoke: no fixture task reuse and no automatic promotion.
            if prepared_plan['extraction_smoke']:
                with Session(engine,expire_on_commit=False) as db:
                    raw=Project(user_id=USER,name='[EVAL] public raw extraction')
                    db.add(raw);db.commit()
                    extraction=[]
                    for relative in ('fastapi/first_steps.py','fastapi/dependencies.py'):
                        source,task,_=ingestion.create_source_and_task_from_bytes(db,settings=native,user_id=USER,project_id=raw.id,
                            filename=Path(relative).name,raw_content=(dataset/'corpus'/relative).read_bytes(),source_type=None,relative_path=relative,repository_id=None)
                        parsing.run_task(db,user_id=USER,task_id=task.id,settings=native)
                        result=knowledge.run_extraction(db,user_id=USER,source_id=source.id,settings=native)
                        candidates=list(db.scalars(select(CandidateKnowledge).where(CandidateKnowledge.source_id==source.id)))
                        extraction.append(dict(source=relative,status=result.task.status,error=result.task.error,
                            candidates=[dict(type=item.candidate_type,name=item.name,summary=item.summary,kind=item.payload['kind'],
                                evidence=item.payload['evidence']) for item in candidates],human_reviewed=False))
                    save(output/'extraction.json',extraction)
            report['model_usage']=meter.summary()
        report['schema_removed']=True
        report['paired_bootstrap']=paired(predictions,cases)
        random.Random(20261026).shuffle(blind)
        rows=[];key={}
        for index,item in enumerate(blind,1):
            review_id=f'review-{index:03}'
            case,prediction=item['case'],item['prediction']
            key[review_id]=dict(mode=item['mode'],case_id=case['id'])
            rows.append(dict(review_id=review_id,question=case['question'],answer=prediction['answer'],
                gold_answer=case['gold_answer'],required_facts=json.dumps(case['required_facts'],ensure_ascii=False),
                citations=json.dumps(prediction['citations'],ensure_ascii=False),reviewer='',answer_correct='',explainability_score=''))
        if rows:
            with (output/'blind-review.csv').open('w',encoding='utf-8-sig',newline='') as file:
                writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        save(output/'grading-key.json',key)
        report['status']='completed_with_case_errors' if report['case_failures'] else 'succeeded'
    except Exception as exc:
        report['status']='failed'
        report['errors'].append(dict(type=type(exc).__name__,code=getattr(exc,'code',None)))
        report['failure_diagnostics']=safe_failure_diagnostics(exc)
        raise
    finally:
        if 'meter' in locals():
            report['model_usage']=meter.summary()
        report['completed_at']=datetime.now(timezone.utc).isoformat()
        save(report_path,report)
    return report


def paired(predictions,cases):
    answerable=[item for item in cases if item['answerable']]
    values={}
    for mode,records in predictions.items():
        by_id={item['id']:item for item in records}
        values[mode]=[len({_evidence_key(e) for e in case['gold_evidence']} &
            {_evidence_key(e) for e in by_id[case['id']]['retrieved_evidence'][:5]})/len(case['gold_evidence']) for case in answerable]
    result={}
    for mode in values:
        if mode=='vector':continue
        differences=[a-b for a,b in zip(values[mode],values['vector'])]
        rng=random.Random(20261026)
        samples=sorted(sum(rng.choice(differences) for _ in differences)/len(differences) for _ in range(2000))
        result[mode+'_minus_vector']=dict(mean=sum(differences)/len(differences),ci95=[samples[49],samples[1949]],
            n=len(differences),method='paired question bootstrap, 2000 samples; small related public examples, not a population guarantee')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,default=Path('../evaluation/public-v2'))
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--allow-model-calls',action='store_true')
    parser.add_argument('--allow-embedding-calls',action='store_true')
    parser.add_argument('--preflight',action='store_true',help='Provider/DB-free plan only; no credentials required')
    parser.add_argument('--model-limit',type=int,default=120)
    parser.add_argument('--embedding-limit',type=int,default=160)
    parser.add_argument('--approved-plan',type=Path,help='Exact reviewed zero-call plan; required for holdout live runs')
    parser.add_argument('--authorization-ledger',type=Path,help='Existing independent user-approved 96/73 holdout grant')
    parser.add_argument('--reuse-answer',type=Path,help='One scoped validated BM25 diagnostic answer; exact evidence must match')
    parser.add_argument('--isolate-output-errors',action='store_true',help='Record invalid output per case without retry; transport errors still stop')
    args=parser.parse_args()
    if args.preflight:
        if args.allow_model_calls or args.allow_embedding_calls:
            parser.error('Preflight must not include provider authorization flags')
        report=plan(args.dataset.resolve(),model_limit=args.model_limit,embedding_limit=args.embedding_limit,
                    authorization_ledger=args.authorization_ledger,reuse_answer=args.reuse_answer,
                    isolate_output_errors=args.isolate_output_errors)
        args.output_dir.mkdir(parents=True,exist_ok=False)
        save(args.output_dir/'run.json',report)
        print(json.dumps(dict(status=report['status'],planned_upper_bounds=report['planned_upper_bounds'],blockers=report['blockers'])))
        raise SystemExit(0)
    if not args.allow_model_calls or not args.allow_embedding_calls:
        parser.error('Both explicit provider authorizations are required')
    try:
        report=run(args.dataset.resolve(),args.output_dir.resolve(),model_limit=args.model_limit,
                   embedding_limit=args.embedding_limit,approved_plan=args.approved_plan,
                   authorization_ledger=args.authorization_ledger,reuse_answer=args.reuse_answer,
                   isolate_output_errors=args.isolate_output_errors)
        print(json.dumps(dict(status=report['status'],models=report['model_usage']['attempted'],embeddings=report['embedding_calls'])))
    except Exception as exc:
        print(f'Public acceptance failed ({type(exc).__name__}); see run.json, never print credentials.')
        raise SystemExit(1)
