"""Compare full versus opt-in summary history JSON in an owned native schema."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.agent_run import AgentRun
from app.models.domain import Project
from app.services.agent_workflows import list_runs
from scripts.isolated_workspace import isolated_workspace


def run(output):
    target=Path(output)
    if target.exists():raise ValueError('Use a new output file')
    owner,project=uuid.uuid4(),uuid.uuid4()
    stamp=datetime(2026,10,30,tzinfo=timezone.utc)
    with isolated_workspace(get_settings()) as (engine,_settings,_schema):
        with Session(engine) as db:
            db.add(Project(id=project,user_id=owner,name='Synthetic workflow payload benchmark'));db.flush()
            for index in range(50):
                db.add(AgentRun(id=uuid.uuid4(),user_id=owner,project_id=project,source_id=None,
                    kind='question_pipeline',status='succeeded',request={'question':'Synthetic','retrieval_mode':'bm25'},
                    input_sha256='a'*64,result={'answer':{'answer':'Synthetic payload. '*200}},usage={'model':2},
                    events=[dict(sequence=i+1,agent='workflow',kind='synthetic',status='saved',elapsed_ms=i) for i in range(256)],
                    created_at=stamp,updated_at=stamp))
            db.commit()
        rows=[]
        for size in (10,50):
            with Session(engine) as db:
                full=list_runs(db,user_id=owner,project_id=project,page=1,page_size=size)
                summary=list_runs(db,user_id=owner,project_id=project,page=1,page_size=size,summary=True)
                assert [item.id for item in full.items]==[item.id for item in summary.items]
                a,b=len(full.model_dump_json().encode()),len(summary.model_dump_json().encode())
                rows.append(dict(page_size=size,full_json_bytes=a,summary_json_bytes=b,reduction_fraction=1-b/a))
    report=dict(protocol='workflow-summary-bytes-v1',provider_calls=0,schemas_removed=True,
        scope='Synthetic envelopes with 256 metadata events and a 3800-character answer; JSON bytes, not HTTP compression/latency.',results=rows)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as file:file.write(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:run(args.output)
    except Exception as exc:raise SystemExit(f'History benchmark failed ({type(exc).__name__}); inspect local configuration without exposing credentials.')
