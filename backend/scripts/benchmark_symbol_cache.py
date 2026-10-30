"""Measure repeated immutable symbol parsing, excluding database/HTTP work."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import time
import tracemalloc
import uuid

from app.analysis.symbol_cache import symbol_cache
from app.services.code_search import _symbols


def run(output,repeats=3):
    target=Path(output)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise ValueError('Use a new output file')
    namespace=uuid.UUID('c2297110-0ba1-4633-a58c-cbe2b7e90b35')
    sources=[SimpleNamespace(user_id=namespace,project_id=namespace,id=uuid.uuid5(namespace,str(i)),
        source_type='java' if i%2 else 'python',content=(
            'class Demo {\n'+''.join(f' void method{j}() {{}}\n' for j in range(30))+'}\n' if i%2
            else ''.join(f'def method{j}():\n    pass\n' for j in range(30)))) for i in range(50)]
    samples=[]
    for index in range(repeats+1):
        if not index:symbol_cache.clear()
        gc.collect();tracemalloc.start();start=time.perf_counter()
        results=[_symbols(source) for source in sources]
        elapsed=(time.perf_counter()-start)*1000
        _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        digest=hashlib.sha256(json.dumps([[str(symbol.id),symbol.name] for result in results
            for symbol in result.symbols]).encode()).hexdigest()
        samples.append(dict(state='cold' if not index else 'warm',elapsed_ms=round(elapsed,3),
            peak_python_bytes=peak,output_sha256=digest,cache=symbol_cache.info()))
    assert len({item['output_sha256'] for item in samples})==1
    payload=dict(protocol='symbol-cache-v1',provider_calls=0,source_count=50,
        scope='Parser/cache calls only; cold first invocation, then repeated keys in one process. Python allocations, not RSS.',samples=samples)
    target.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    symbol_cache.clear()
    return payload


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.output)
