import json
import uuid
from app.tools.chunks import ChunkTools
from app.tools.evidence import EvidenceTools
from app.core.errors import AppError
from app.agents.runtime import RunContext, embedding_attempt, run_scope
from tests.test_knowledge import configured
from tests.test_questions import prepared_project
from app.services import questions
from app.services.search import search_knowledge


def test_chunk_tools_are_bounded_and_do_not_read_arbitrary_files():
    identifier=str(uuid.uuid4());tools=ChunkTools([dict(chunk_id=identifier,content='x'*7000)])
    assert tools.execute('shell','{}')=={'error':'TOOL_NOT_ALLOWED'}
    assert tools.execute('read_chunk','{}')=={'error':'INVALID_ARGUMENTS'}
    assert tools.execute('read_chunk',None)=={'error':'INVALID_ARGUMENTS'}
    assert tools.execute('read_chunk',json.dumps(dict(chunk_id=str(uuid.uuid4()))))=={'error':'CHUNK_OUT_OF_SCOPE'}
    result=tools.execute('read_chunk',json.dumps(dict(chunk_id=identifier)))
    assert len(result['content'])==6000 and result['truncated']


def test_evidence_search_read_scope_and_error_handling(client,db_session,configured,monkeypatch):
    project,settings=prepared_project(client,monkeypatch)
    from app.api.dependencies import get_current_user_id
    from app.core.identity import DEVELOPMENT_USER_ID
    records,_=questions.collect_evidence(search_knowledge(db_session,user_id=DEVELOPMENT_USER_ID,project_id=uuid.UUID(project),
        query='PostgreSQL',mode='bm25',types=[],valid_at=None,top_k=5,settings=settings))
    seen=[]
    def search(query,mode):seen.append((query,mode));return records
    tools=EvidenceTools(search,{})
    assert tools.execute('search_knowledge',json.dumps(dict(query='PostgreSQL',mode='bm25')))['evidence']
    assert seen==[('PostgreSQL','bm25')]
    assert tools.execute('read_evidence',json.dumps(dict(evidence_id=str(next(iter(records))))))['quote']
    assert tools.execute('read_evidence',json.dumps(dict(evidence_id=str(uuid.uuid4()))))=={'error':'EVIDENCE_OUT_OF_SCOPE'}
    assert tools.execute('shell','{}')=={'error':'TOOL_NOT_ALLOWED'}
    assert tools.execute('search_knowledge',json.dumps(dict(query='   ')))=={'error':'INVALID_ARGUMENTS'}
    assert tools.execute('search_knowledge','invalid')=={'error':'INVALID_ARGUMENTS'}
    assert tools.execute('read_evidence',None)=={'error':'INVALID_ARGUMENTS'}
    def fail(*_):raise AppError(status_code=503,code='EMBEDDING_NOT_CONFIGURED',message='private details')
    tools.search=fail
    assert tools.execute('search_knowledge',json.dumps(dict(query='test')))=={'error':'EMBEDDING_NOT_CONFIGURED'}


def test_embedding_requests_have_their_own_shared_budget():
    import pytest
    context=RunContext(user_id=uuid.uuid4(),project_id=uuid.uuid4(),embedding_limit=1)
    with run_scope(context):
        embedding_attempt()
        with pytest.raises(AppError):embedding_attempt()
    assert context.counts['embedding']==1
