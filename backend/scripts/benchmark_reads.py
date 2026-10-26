"""Measure local read paths in a disposable native PostgreSQL schema; no providers."""
import argparse
from datetime import datetime, timedelta, timezone
import gc
import hashlib
import json
from pathlib import Path
import statistics
import time
import tracemalloc
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app import models
from app.core import config as app_config
from app.db.base import Base
from app.models.domain import CandidateKnowledge, ProcessingTask, Project, SourceChunk, SourceDocument, TaskStatus
from app.schemas.knowledge import ReviewResolve
from app.services import knowledge, search
from app.api.routes.sources import list_sources

NAMESPACE = uuid.UUID('233bdce9-e0ab-495f-a92c-6d457016e007')
USER = uuid.uuid5(NAMESPACE, 'user')
PROJECT = uuid.uuid5(NAMESPACE, 'project')


def seed(db, count=100, history=20, body_bytes=131072):
    """Synthetic candidates pass the normal explicit review/promotion service."""
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.add(Project(id=PROJECT, user_id=USER, name='Synthetic read benchmark', created_at=stamp, updated_at=stamp))
    db.flush()
    for index in range(count):
        source_id = uuid.uuid5(NAMESPACE, f'source-{index}')
        chunk_id = uuid.uuid5(source_id, 'chunk')
        task_id = uuid.uuid5(source_id, 'extraction')
        quote = f'PostgreSQL stores synthetic record {index}.'
        body = quote + '\n' + 'x' * body_bytes
        db.add(SourceDocument(id=source_id, user_id=USER, project_id=PROJECT, original_name=f'note-{index}.md',
            media_type='text/markdown', source_type='markdown', size_bytes=len(body), content=body,
            content_sha256=hashlib.sha256(body.encode()).hexdigest(), status='ready', created_at=stamp, updated_at=stamp))
        db.flush()
        db.add(SourceChunk(id=chunk_id, user_id=USER, project_id=PROJECT, source_id=source_id, position=0,
            kind='paragraph', content=quote, heading_path=[], start_line=1, end_line=1,
            content_sha256=hashlib.sha256(quote.encode()).hexdigest()))
        db.add(ProcessingTask(id=task_id, user_id=USER, project_id=PROJECT, source_id=source_id,
            type='knowledge_candidates', status=TaskStatus.SUCCEEDED))
        for attempt in range(history):
            db.add(ProcessingTask(id=uuid.uuid5(source_id, f'parse-{attempt}'), user_id=USER, project_id=PROJECT,
                source_id=source_id, type='markdown_parsing', status=TaskStatus.SUCCEEDED,
                error={'synthetic_padding': 'x' * 4096}, created_at=stamp + timedelta(seconds=attempt)))
        db.flush()
        candidate_id = uuid.uuid5(source_id, 'candidate')
        db.add(CandidateKnowledge(id=candidate_id, user_id=USER, project_id=PROJECT, source_id=source_id,
            task_id=task_id, candidate_type='Decision', name=f'PostgreSQL {index:03}', summary=quote, confidence=.9,
            payload={'kind':'entity', 'evidence':[{'chunk_id':str(chunk_id), 'quote':quote,
                'start_line':1, 'end_line':1, 'heading_path':[]}]}))
        db.flush()
        knowledge.resolve_review(db, user_id=USER, review_id=candidate_id, decision=ReviewResolve(action='confirm'))


def measure(engine, operation, repeats):
    samples, signature = [], None
    for _ in range(repeats):
        gc.collect()
        queries = []
        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            queries.append(statement)
        with engine.connect() as connection, Session(bind=connection) as db:
            event.listen(connection, 'before_cursor_execute', capture)
            tracemalloc.start()
            started = time.perf_counter()
            result = operation(db)
            value = result.model_dump(mode='json', exclude={'items': {'__all__': {'entity': {'valid_from', 'created_at', 'updated_at'}}}})
            elapsed = (time.perf_counter() - started) * 1000
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            event.remove(connection, 'before_cursor_execute', capture)
            # Compare stable semantic output, excluding fixture wall-clock timestamps.
            encoded = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
            current = hashlib.sha256(encoded).hexdigest()
            if signature is not None:
                assert signature == current
            signature = current
            samples.append(dict(queries=len(queries), elapsed_ms=round(elapsed, 3), peak_python_bytes=peak))
    return dict(samples=samples, median_ms=round(statistics.median(item['elapsed_ms'] for item in samples), 3),
                max_peak_python_bytes=max(item['peak_python_bytes'] for item in samples), output_sha256=signature)


def run(output, repeats):
    settings = app_config.get_settings()
    base = make_url(settings.database_url)
    if base.get_backend_name() != 'postgresql':
        raise ValueError('Native PostgreSQL is required')
    schema = 'ka_benchmark_' + uuid.uuid4().hex
    admin = create_engine(base)
    url = base.set(query={**base.query, 'options': f'-csearch_path={schema},public'})
    engine, previous, created = None, app_config.get_settings, False
    try:
        with admin.begin() as connection:
            revision = connection.scalar(text('SELECT version_num FROM public.alembic_version'))
            version = connection.scalar(text('SHOW server_version'))
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
        config = Config('alembic.ini')
        config.attributes['version_table_schema'] = schema
        app_config.get_settings = lambda: settings.model_copy(update={'database_url':url.render_as_string(hide_password=False).replace('%','%%')})
        command.upgrade(config, 'head')
        app_config.get_settings = previous
        engine = create_engine(url)
        with engine.begin() as connection:
            owned = set(connection.scalars(text('SELECT table_name FROM information_schema.tables WHERE table_schema=:schema'), {'schema':schema}))
            assert set(Base.metadata.tables).issubset(owned)
            assert connection.scalar(text('SELECT count(*) FROM public.projects WHERE id=:id'), {'id':PROJECT}) == 0
        with Session(engine) as db:
            seed(db)
        operations = {}
        for size in (20, 100):
            operations[f'sources_page_{size}'] = measure(engine, lambda db, size=size: list_sources(
                PROJECT, db, USER, page=1, page_size=size, q='', source_type=None, source_status=None), repeats)
        for mode in ('keyword', 'bm25', 'bm25_source'):
            for size in (1, 10, 50):
                operations[f'{mode}_top_{size}'] = measure(engine, lambda db, mode=mode, size=size: search.search_knowledge(
                    db, user_id=USER, project_id=PROJECT, query='PostgreSQL', types=[], valid_at=None,
                    top_k=size, mode=mode, settings=settings), repeats)
        payload = dict(protocol='native-read-path-v1', database_version=version,
            fixture={'sources':100, 'body_padding_bytes':131072, 'parsing_tasks_per_source':20, 'entities':100},
            timing_scope='service+serialization; connection acquisition excluded; Python allocations, not RSS/server memory',
            providers=0, operations=operations)
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({name:{'queries':value['samples'][0]['queries'], 'median_ms':value['median_ms'],
            'peak_bytes':value['max_peak_python_bytes']} for name,value in operations.items()}))
    finally:
        app_config.get_settings = previous
        if engine:
            engine.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                assert connection.scalar(text('SELECT version_num FROM public.alembic_version')) == revision
                assert connection.scalar(text('SELECT count(*) FROM public.projects WHERE id=:id'), {'id':PROJECT}) == 0
        admin.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--repeats', type=int, choices=range(1, 11), default=3)
    args = parser.parse_args()
    try:
        run(args.output, args.repeats)
    except Exception as error:
        raise SystemExit(f'Benchmark failed ({type(error).__name__}); no credentials logged')
