import uuid

import pytest
from sqlalchemy import event, inspect

from app.api.routes.sources import list_sources
from app.services import graph, ingestion, search
from app.core.config import Settings
from scripts.benchmark_reads import PROJECT, USER, seed


def test_source_projection_and_latest_tasks_are_bounded(db_session):
    seed(db_session, count=12, history=8, body_bytes=65536)
    db_session.expunge_all()
    statements = []
    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)
    engine = db_session.get_bind()
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        response = list_sources(PROJECT, db_session, USER, page=1, page_size=10, q='', source_type=None, source_status=None)
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert len(response.items) == 10 and response.total == 12
    assert len(statements) == 8  # Includes four batched Git provenance queries.
    assert not any('source_documents.content' in sql or 'processing_tasks.error' in sql for sql in statements)
    records, _ = ingestion.list_sources(db_session, user_id=USER, project_id=PROJECT, page=1, page_size=10)
    for source, task in records:
        assert 'content' in inspect(source).unloaded
        assert task.id == uuid.uuid5(source.id, 'parse-7')
        assert 'error' in inspect(task).unloaded


@pytest.mark.parametrize('mode,expected', [('keyword',8), ('bm25',10), ('bm25_source',10)])
def test_search_query_count_does_not_grow_per_hit_and_evidence_is_unchanged(db_session, mode, expected):
    seed(db_session, count=12, history=1, body_bytes=1024)
    engine = db_session.get_bind()
    counts = []
    for size in (1, 10):
        db_session.expunge_all()
        statements = []
        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            if statement.lstrip().upper().startswith('SELECT'):
                statements.append(statement)
        event.listen(engine, 'before_cursor_execute', capture)
        try:
            result = search.search_knowledge(db_session, user_id=USER, project_id=PROJECT, query='PostgreSQL',
                types=[], valid_at=None, top_k=size, mode=mode, settings=Settings())
        finally:
            event.remove(engine, 'before_cursor_execute', capture)
        counts.append(len(statements))
        assert len(result.items) == size
        for hit in result.items:
            assert hit.evidence[0].quote == hit.entity.summary
            assert str(hit.evidence[0].source_id) in hit.evidence[0].uri
    assert counts == [expected, expected]
    assert graph.evidence_for_records(db_session, []) == {}
