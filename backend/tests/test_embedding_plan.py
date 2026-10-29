import hashlib
import uuid

from sqlalchemy import event, select

from app.models.graph import KnowledgeEntity
from app.services import embeddings
from tests.test_knowledge import configured
from tests.test_questions import prepared_project


def test_plan_bulk_evidence_and_reuse_preserve_owner_digests(client, db_session, configured, monkeypatch):
    project, settings = prepared_project(client, monkeypatch)
    entity = db_session.scalar(select(KnowledgeEntity).where(KnowledgeEntity.project_id == uuid.UUID(project)))
    entity.summary += ' A changed fact.'
    db_session.commit()
    statements=[]
    def capture(_connection, _cursor, statement, *_args):
        statements.append(statement)
    event.listen(db_session.get_bind(), 'before_cursor_execute', capture)
    try:
        count, pending = embeddings.plan_project_embeddings(db_session, user_id=entity.user_id,
            project_id=uuid.UUID(project), settings=settings)
    finally:
        event.remove(db_session.get_bind(), 'before_cursor_execute', capture)
    assert count == 2 and len(pending) == 1 and pending[0][0] == entity.id
    assert pending[0][2] == hashlib.sha256(pending[0][1].encode()).hexdigest()
    assert sum('FROM knowledge_evidence' in statement for statement in statements) == 1
    calls=[]
    def fake(_settings, texts):
        calls.extend(texts)
        return [[1.0]+[0.0]*1023 for _ in texts]
    monkeypatch.setattr(embeddings, 'embed_texts', fake)
    result = embeddings.rebuild_project_embeddings(db_session, user_id=entity.user_id,
        project_id=uuid.UUID(project), settings=settings)
    assert result['updated_count'] == 1 and result['reused_count'] == 1 and calls == [pending[0][1]]
    assert embeddings.rebuild_project_embeddings(db_session, user_id=entity.user_id,
        project_id=uuid.UUID(project), settings=settings)['updated_count'] == 0
    assert len(calls) == 1
