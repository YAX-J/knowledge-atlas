"""Run the new public corpus through the real online question service in an owned schema.

Explicit budgets, immutable corpus/index fingerprints, partial outputs and human
grades remaining empty are mandatory. No retry, private inputs or application writes.
"""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
import time
import uuid
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.identity import DEVELOPMENT_USER_ID as USER
from app.models.domain import CandidateKnowledge, Project
from app.services import embeddings, ingestion, knowledge, model_usage, parsing, questions
from app.services.search import search_knowledge
from scripts.evaluate_dataset import _evidence_key, score_predictions, validate_dataset
from scripts.evaluation_snapshot import project_snapshot
from scripts.isolated_workspace import isolated_workspace
from scripts.prepare_evaluation import prepare_project
from scripts.run_evaluation import _evidence_record, ordered_evidence
from scripts.provider_ledger import ProviderLedger


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def run(dataset,output,*,model_limit=120,embedding_limit=160):
    if output.exists():
        raise ValueError('Output directory must be new')
    manifest,cases,summary=validate_dataset(dataset)
    protocol=json.loads((dataset/'protocol.json').read_text(encoding='utf-8'))
    if protocol['dataset']!=summary:
        raise ValueError('Frozen protocol fingerprint changed')
    # This command deliberately accepts only the public, provenance-pinned pack.
    if summary['dataset_id']!='knowledge-atlas-public-v2':
        raise ValueError('Only the approved public-v2 dataset is allowed')
    settings=get_settings()
    if not settings.deepseek_api_key or not settings.embedding_api_key:
        raise ValueError('Providers are not configured')
    if not 1<=model_limit<=120 or not 1<=embedding_limit<=160:
        raise ValueError('Budget exceeds the user authorization')
    output.mkdir(parents=True)
    report=dict(status='running',protocol='public-online-v2',dataset=summary,
        started_at=datetime.now(timezone.utc).isoformat(),private_inputs=False,human_coverage=0,
        billing_cost=None,embedding_calls=0,model_limit=model_limit,embedding_limit=embedding_limit,
        schema_removed=False,modes={},errors=[])
    report_path=output/'run.json'
    save(report_path,report)
    original_embedding=embeddings.embed_texts
    original_begin=model_usage.begin_call
    ledger=ProviderLedger(Path(__file__).resolve().parents[2]/'output/completeness-20261026/provider-budget.json')
    original_search=questions.search_knowledge
    captured={}
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
        ledger.reserve(kind)
        original_begin(kind)
    def capture_search(*args,**kwargs):
        result=original_search(*args,**kwargs)
        captured['result']=result
        return result
    try:
        with model_usage.usage_budget(model_limit) as meter, patch.object(model_usage,'begin_call',measured_begin), patch.object(embeddings,'embed_texts',measured_embedding), isolated_workspace(settings) as (engine,native,schema):
            report['model_usage']=meter.summary()
            project_id=uuid.uuid4()
            prepared=prepare_project(engine=engine,dataset_root=dataset,project_id=project_id,settings=native,accept_curated_fixture=True)
            save(output/'preparation.json',prepared)
            with Session(engine,expire_on_commit=False) as db:
                index=embeddings.rebuild_project_embeddings(db,user_id=USER,project_id=project_id,settings=native)
            report['index']=index
            mapping={uuid.UUID(value):path for path,value in prepared['source_ids'].items()}
            with Session(engine) as db:
                frozen=project_snapshot(db,user_id=USER,project_id=project_id)
            report['snapshot']=frozen
            for mode in protocol['modes']:
                records=[]
                partial=output/f'{mode}.partial.jsonl'
                for case in cases:
                    began=time.perf_counter()
                    with Session(engine) as db:
                        if mode=='keyword':
                            result=search_knowledge(db,user_id=USER,project_id=project_id,query=case['question'],types=[],valid_at=None,top_k=5,mode=mode,settings=native)
                            answer,supported,citations=None,None,[]
                        else:
                            with patch.object(questions,'search_knowledge',capture_search):
                                response=questions.answer_question(db,user_id=USER,project_id=project_id,question=case['question'],valid_at=None,
                                    settings=native,retrieval_mode=mode)
                            result=captured['result']
                            answer,supported=response.answer,response.supported
                            citations=[_evidence_record(item,mapping) for item in response.evidence]
                        prediction=dict(id=case['id'],retrieved_evidence=[_evidence_record(item,mapping) for item in ordered_evidence(result)],
                            citations=citations,answer=answer,supported=supported,latency_ms=round((time.perf_counter()-began)*1000,3),
                            answer_correct=None,explainability_score=None)
                    records.append(prediction)
                    with partial.open('a',encoding='utf-8') as file:
                        file.write(json.dumps(prediction,ensure_ascii=False)+'\n')
                    if mode!='keyword':
                        blind.append(dict(mode=mode,case=case,prediction=prediction))
                    report['model_usage']=meter.summary()
                    save(report_path,report)
                    print(f"{mode} {case['id']}: saved; model={len(meter.calls)}, embedding={report['embedding_calls']}",flush=True)
                metrics=score_predictions(cases=cases,predictions=records)
                save(output/f'{mode}.metrics.json',metrics)
                partial.rename(output/f'{mode}.jsonl')
                report['modes'][mode]=metrics
                predictions[mode]=records
                with Session(engine) as db:
                    if project_snapshot(db,user_id=USER,project_id=project_id)!=frozen:
                        raise RuntimeError('Knowledge/index changed during evaluation')
                save(report_path,report)
            # Independent extraction smoke: no fixture task reuse and no automatic promotion.
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
        with (output/'blind-review.csv').open('w',encoding='utf-8-sig',newline='') as file:
            writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        save(output/'grading-key.json',key)
        report['status']='succeeded'
    except Exception as exc:
        report['status']='failed'
        report['errors'].append(dict(type=type(exc).__name__,code=getattr(exc,'code',None)))
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
    args=parser.parse_args()
    if not args.allow_model_calls or not args.allow_embedding_calls:
        parser.error('Both explicit provider authorizations are required')
    try:
        report=run(args.dataset.resolve(),args.output_dir.resolve())
        print(json.dumps(dict(status=report['status'],models=report['model_usage']['attempted'],embeddings=report['embedding_calls'])))
    except Exception as exc:
        print(f'Public acceptance failed ({type(exc).__name__}); see run.json, never print credentials.')
        raise SystemExit(1)
