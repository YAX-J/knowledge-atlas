"""Explicit real-model/native call acceptance on pinned public PetClinic code; not human quality grades."""
import argparse
import json
from pathlib import Path
import uuid
from unittest.mock import patch
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.identity import DEVELOPMENT_USER_ID as USER
from app.services import code_agent,model_usage
from scripts.evaluate_dataset import validate_dataset
from scripts.isolated_workspace import isolated_workspace
from scripts.prepare_evaluation import prepare_project
from scripts.provider_ledger import ProviderLedger


def run(dataset,output):
    _,_,summary=validate_dataset(dataset)
    if summary['dataset_id']!='knowledge-atlas-public-v2':
        raise ValueError('Only the approved pinned public corpus is accepted')
    if output.exists():raise FileExistsError('Use a new result directory')
    output.mkdir(parents=True)
    def line(path,needle):
        rows=(dataset/'corpus'/path).read_text(encoding='utf-8').splitlines()
        found=[number for number,text in enumerate(rows,1) if needle in text]
        if len(found)!=1:raise ValueError('Public call gold must locate a unique line')
        return found[0]
    protocol=dict(source='petclinic/Owner.java',call_line=line('petclinic/Owner.java','pet.addVisit(visit);'),
        target='petclinic/Pet.java',declaration_line=line('petclinic/Pet.java','public void addVisit('),
        scope='Four same-repository public Java source files, incomplete Spring/JPA classpath; one source-verified positive acceptance case, not general accuracy')
    report=dict(status='running',dataset=summary,case=protocol,human_reviewed=False,results={},schema_removed=False)
    def save():
        (output/'run.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save()
    ledger=ProviderLedger(Path(__file__).resolve().parents[2]/'output/completeness-20261026/provider-budget.json')
    original=model_usage.begin_call
    def begin(kind):ledger.reserve(kind);original(kind)
    try:
        with model_usage.usage_budget(12) as meter,patch.object(model_usage,'begin_call',begin),isolated_workspace(get_settings()) as (engine,native,schema):
            prepared=prepare_project(engine=engine,dataset_root=dataset,project_id=uuid.uuid4(),settings=native,accept_curated_fixture=True)
            source_id=uuid.UUID(prepared['source_ids']['corpus/petclinic/Owner.java'])
            for strategy in ('single_step','tools','semantic'):
                with Session(engine) as db:
                    result=code_agent.analyze_calls(db,user_id=USER,source_id=source_id,settings=native,strategy=strategy)
                targets={item.id:item for item in result.related_symbols}
                found=any(call.line==protocol['call_line'] and any(targets[key].source_path==protocol['target'] and
                    targets[key].start_line==protocol['declaration_line'] for key in call.target_ids) for call in result.calls)
                report['results'][strategy]=dict(source_verified_target_found=found,provider_calls=result.provider_call_count,
                    tool_calls=result.tool_call_count,uncovered_call_count=result.uncovered_call_count,truncated=result.truncated,
                    candidate_generation=result.candidate_generation,semantic_diagnostics=result.semantic_diagnostics)
                (output/f'{strategy}.json').write_text(result.model_dump_json(indent=2),encoding='utf-8')
                report['model_usage']=meter.summary();save()
                print(f'{strategy}: target_found={found}, provider_calls={result.provider_call_count}',flush=True)
            report['model_usage']=meter.summary()
        report['schema_removed']=True
        report['status']='succeeded'
    except Exception as exc:
        report['status']='failed';report['error']=dict(type=type(exc).__name__,code=getattr(exc,'code',None));raise
    finally:
        if 'meter' in locals():report['model_usage']=meter.summary()
        save()
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,default=Path('../evaluation/public-v2'))
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--allow-model-calls',action='store_true')
    args=parser.parse_args()
    if not args.allow_model_calls:parser.error('Explicit provider authorization is required')
    try:run(args.dataset.resolve(),args.output_dir.resolve())
    except Exception as exc:
        print(f'Public call acceptance failed ({type(exc).__name__}); see the safe run report.');raise SystemExit(1)
