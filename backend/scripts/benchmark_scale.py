"""Measure 1k/10k reviewed synthetic entities in owned native schemas, without providers."""
import argparse
import gc
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
import tracemalloc
from unittest.mock import patch

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.graph import KnowledgeEmbedding, KnowledgeEntity, KnowledgeEvidence
from app.services import embeddings, search
from scripts.benchmark_reads import PROJECT, USER, seed
from scripts.isolated_workspace import isolated_workspace


def original_plan(db, settings):
    """Frozen pre-optimization algorithm; output compared against production planner."""
    entities = list(db.scalars(select(KnowledgeEntity).where(KnowledgeEntity.user_id == USER,
        KnowledgeEntity.project_id == PROJECT, KnowledgeEntity.status != 'archived').order_by(KnowledgeEntity.id)))
    existing = {row.entity_id: row for row in db.scalars(select(KnowledgeEmbedding).where(
        KnowledgeEmbedding.user_id == USER, KnowledgeEmbedding.project_id == PROJECT))}
    pending = []
    for entity in entities:
        quotes = list(db.scalars(select(KnowledgeEvidence.quote).where(KnowledgeEvidence.entity_id == entity.id,
            KnowledgeEvidence.user_id == USER, KnowledgeEvidence.project_id == PROJECT).order_by(KnowledgeEvidence.id)))
        body = embeddings.entity_text(entity, quotes)
        digest = hashlib.sha256(body.encode()).hexdigest()
        current = existing.get(entity.id)
        if not current or current.model != settings.embedding_model or current.dimensions != settings.embedding_dimensions or current.content_sha256 != digest:
            pending.append((entity.id, body, digest))
    return len(entities), pending


def measure(engine, operation, repeats, serialize=lambda value: value):
    def once(record):
        gc.collect()
        queries = 0
        def capture(*_args):
            nonlocal queries
            queries += 1
        with engine.connect() as connection, Session(bind=connection) as db:
            event.listen(connection, 'before_cursor_execute', capture)
            tracemalloc.start()
            started = time.perf_counter()
            value = serialize(operation(db))
            elapsed = (time.perf_counter() - started) * 1000
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            event.remove(connection, 'before_cursor_execute', capture)
            digest = hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()
        return dict(sql_queries=queries, elapsed_ms=round(elapsed, 3), peak_python_bytes=peak, output_sha256=digest)
    once(False)  # Warm-up excluded. No process/server restart; no cold-cache claim.
    samples = [once(True) for _ in range(repeats)]
    assert len({item['output_sha256'] for item in samples}) == 1
    elapsed = sorted(item['elapsed_ms'] for item in samples)
    return dict(samples=samples, median_ms=statistics.median(elapsed), p95_ms=elapsed[math.ceil(.95*len(elapsed))-1],
        sql_queries=samples[0]['sql_queries'], max_peak_python_bytes=max(item['peak_python_bytes'] for item in samples),
        output_sha256=samples[0]['output_sha256'])


def run(output, repeats):
    results = []
    settings = get_settings()
    def forbidden(*_args, **_kwargs):
        raise AssertionError('Benchmark must never contact a provider')
    for count in (1000, 10000):
        with isolated_workspace(settings) as (engine, native, _schema):
            with Session(engine) as db:
                seed(db, count=count, history=0, body_bytes=0)
            print(json.dumps({'seeded_reviewed_entities': count}), flush=True)
            with patch('httpx.post', forbidden), patch.object(embeddings, 'embed_texts', forbidden):
                before = measure(engine, lambda db: original_plan(db, native), repeats)
                after = measure(engine, lambda db: embeddings.plan_project_embeddings(db,
                    user_id=USER, project_id=PROJECT, settings=native), repeats)
                assert before['output_sha256'] == after['output_sha256']
                reads = {mode: measure(engine, lambda db, mode=mode: search.search_knowledge(db,
                    user_id=USER, project_id=PROJECT, query='PostgreSQL', types=[], valid_at=None,
                    top_k=10, mode=mode, settings=native), repeats,
                    lambda value: value.model_dump(mode='json')) for mode in ('keyword', 'bm25', 'bm25_source')}
                with Session(engine) as db:
                    _, pending = embeddings.plan_project_embeddings(db, user_id=USER, project_id=PROJECT, settings=native)
                    characters = sum(len(item[1]) for item in pending)
                results.append(dict(entities=count, before=before, after=after, reads=reads,
                    cost=dict(actual_model_requests=0, actual_embedding_requests=0,
                        cold_index_texts=count, cold_index_embedding_batches=math.ceil(count/native.embedding_batch_size),
                        embedding_batch_size=native.embedding_batch_size, cold_index_input_characters=characters,
                        unchanged_index_embedding_batches=0,
                        money='Not estimated: tokenizer, provider rate and reported usage required.')))
            print(json.dumps({'completed_entities': count, 'before_queries':before['sql_queries'],
                'after_queries':after['sql_queries'], 'before_p95_ms':before['p95_ms'], 'after_p95_ms':after['p95_ms']}), flush=True)
    payload = dict(protocol='native-scale-v1', repeats=repeats, providers=0,
        fixture='Synthetic candidates confirmed through ordinary explicit review; 1 source/chunk/evidence per entity; no history padding.',
        scope='Warm local service calls. Python tracemalloc peak, not RSS/PostgreSQL memory. Planning excludes embedding transport/vector persistence. BM25 keeps production scan limits.',
        results=results)
    target=Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--repeats', type=int, choices=range(20, 51), default=20)
    args=parser.parse_args()
    run(args.output, args.repeats)
