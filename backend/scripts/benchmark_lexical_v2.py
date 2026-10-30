"""Versioned warm native lexical v2 measurements; owned schemas and zero providers."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import statistics
import time
import tracemalloc
from unittest.mock import patch

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services import embeddings, lexical, search
from scripts.benchmark_reads import PROJECT, USER, seed
from scripts.isolated_workspace import isolated_workspace


def measure(engine, settings, mode, query, repeats):
    samples=[]
    metadata=None
    for index in range(repeats+1):
        gc.collect()
        queries=[]
        def capture(_conn,_cursor,sql,*_args):
            if sql.lstrip().upper().startswith('SELECT'):queries.append(1)
        with engine.connect() as connection, Session(bind=connection) as db:
            event.listen(connection,'before_cursor_execute',capture)
            tracemalloc.start()
            try:
                start=time.perf_counter()
                result=search.search_knowledge(db,user_id=USER,project_id=PROJECT,query=query,
                    types=[],valid_at=None,top_k=10,mode=mode,settings=settings)
                value=result.model_dump(mode='json')
                elapsed=(time.perf_counter()-start)*1000
                _,peak=tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
                event.remove(connection,'before_cursor_execute',capture)
        metadata=value['lexical']
        if index:
            samples.append(dict(selects=len(queries),elapsed_ms=round(elapsed,3),peak_python_bytes=peak,
                output_sha256=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()))
    assert len({item['output_sha256'] for item in samples})==1
    return dict(query=query,mode=mode,samples=samples,median_ms=statistics.median(item['elapsed_ms'] for item in samples),
        max_peak_python_bytes=max(item['peak_python_bytes'] for item in samples),lexical=metadata)


def run(output, repeats=3, counts=(1000,10000)):
    target=Path(output)
    target.mkdir(parents=True,exist_ok=False)
    report=dict(protocol='native-lexical-v2-20261030',status='running',repeats=repeats,
        lexical_protocols=[lexical.PROTOCOL,lexical.SOURCE_PROTOCOL],provider_calls=0,
        fixture='Synthetic candidates promoted through ordinary explicit review, one exact quote per entity.',
        measurement='Warm local service calls, one excluded warm-up; tracemalloc Python allocations, not RSS/DB/HTTP latency.',
        results=[],schemas_removed=False)
    def save(): (target/'run.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    def forbidden(*_args,**_kwargs):raise AssertionError('No providers in lexical benchmarks')
    save()
    try:
        for count in counts:
            with isolated_workspace(get_settings()) as (engine,native,_schema):
                with Session(engine) as db:seed(db,count=count,history=0,body_bytes=0)
                print(f'Seeded {count} reviewed synthetic entities',flush=True)
                with patch.object(embeddings,'embed_texts',forbidden):
                    reads=[measure(engine,native,mode,query,repeats) for mode in ('bm25','bm25_source')
                        for query in ('PostgreSQL',f'record {count-1}')]
                assert all(item['lexical']['scanned_count']==count for item in reads)
                report['results'].append(dict(entities=count,reads=reads))
            save()
            print(f'Measured {count}; owned schema removed',flush=True)
        report.update(status='succeeded',schemas_removed=True)
    except Exception as exc:
        report.update(status='failed',error_type=type(exc).__name__)
        raise
    finally:save()
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--repeats',type=int,choices=range(3,21),default=3)
    args=parser.parse_args()
    try:run(args.output,args.repeats)
    except Exception as exc:raise SystemExit(f'Lexical benchmark failed ({type(exc).__name__}); inspect local configuration without exposing credentials.')
