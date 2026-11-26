"""Paired native batch-size measurements; no ranking, dataset or provider changes."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import statistics
import time
import tracemalloc
from unittest.mock import patch

import httpx
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.domain import utc_now
from app.services import embeddings, search
from scripts.benchmark_reads import PROJECT, USER, seed
from scripts.isolated_workspace import isolated_workspace


def measure(engine, settings, mode, query, batch_size, at, repeats):
    samples = []
    fingerprints = set()
    for index in range(repeats + 1):
        gc.collect()
        selects = 0

        def capture(_connection, _cursor, sql, *_args):
            nonlocal selects
            if sql.lstrip().upper().startswith('SELECT'):
                selects += 1

        with Session(engine) as db, patch.object(search, 'BM25_BATCH_SIZE', batch_size):
            connection = db.connection()
            event.listen(connection, 'before_cursor_execute', capture)
            tracemalloc.start()
            try:
                started = time.perf_counter()
                result = search.search_knowledge(
                    db, user_id=USER, project_id=PROJECT, query=query, types=[], valid_at=at,
                    top_k=10, mode=mode, settings=settings,
                ).model_dump(mode='json')
                elapsed = (time.perf_counter() - started) * 1000
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
                event.remove(connection, 'before_cursor_execute', capture)
        result['lexical'].pop('batch_size')
        digest = hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        fingerprints.add(digest)
        if index:
            samples.append(dict(elapsed_ms=round(elapsed, 3), selects=selects, peak_python_bytes=peak))
    if len(fingerprints) != 1:
        raise AssertionError('Repeated lexical output changed')
    return dict(
        mode=mode, query=query, batch_size=batch_size, semantic_sha256=next(iter(fingerprints)),
        median_ms=statistics.median(sample['elapsed_ms'] for sample in samples), samples=samples,
        peak_python_bytes=max(sample['peak_python_bytes'] for sample in samples),
    )


def run(output, counts, repeats):
    target = Path(output)
    target.mkdir(parents=True, exist_ok=False)
    report = dict(
        protocol='lexical-batch-paired-v1', provider_calls=0, status='running', results=[], schemas_removed=False,
        repeats=repeats, batch_sizes=[200, 500],
        note='Same native fixture/time/query; one warmup excluded. Median, not p95/SLA. Python allocations are not RSS.',
        search_sha256=hashlib.sha256(Path(search.__file__).read_bytes()).hexdigest(),
    )

    def save():
        (target / 'run.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def blocked(*_args, **_kwargs):
        raise AssertionError('Lexical measurement forbids providers')

    save()
    try:
        with patch.object(httpx.HTTPTransport, 'handle_request', blocked), patch.object(embeddings, 'embed_texts', blocked):
            for count in counts:
                with isolated_workspace(get_settings()) as (engine, settings, _schema):
                    with Session(engine) as db:
                        seed(db, count=count, history=0, body_bytes=0)
                    at = utc_now()
                    print(f'Paired lexical fixture: {count} entities', flush=True)
                    for mode in ('bm25','bm25_source'):
                        pairs = [measure(engine, settings, mode, 'PostgreSQL', size, at, repeats) for size in (200, 500)]
                        if pairs[0]['semantic_sha256'] != pairs[1]['semantic_sha256']:
                            raise AssertionError('Batch size changed ranking or evidence')
                        report['results'].append(dict(entities=count, mode=mode, paired=pairs))
                        save()
                print(f'Fixture {count} cleaned', flush=True)
        report.update(status='succeeded', schemas_removed=True)
    except Exception:
        report['status'] = 'failed'
        save()
        raise
    save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--counts', nargs='+', type=int, default=[1000, 10000])
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20 or any(not 1 <= count <= 50000 for count in args.counts):
        parser.error('Invalid bounds')
    run(args.output, args.counts, args.repeats)


if __name__ == '__main__':
    main()
