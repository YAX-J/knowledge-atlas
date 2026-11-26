from datetime import timedelta
import uuid

from sqlalchemy import delete,func,select

from app.api.routes import search as routes
from app.models.domain import utc_now
from app.models.embedding_job import EmbeddingJob
from app.models.graph import KnowledgeEmbedding
from app.services import embeddings
from tests.test_knowledge import configured
from tests.test_questions import prepared_project


def setup(client,db_session,monkeypatch):
    project,settings=prepared_project(client,monkeypatch)
    settings=settings.model_copy(update={'embedding_batch_size':1})
    monkeypatch.setattr(routes,'get_settings',lambda:settings)
    db_session.execute(delete(KnowledgeEmbedding).where(KnowledgeEmbedding.project_id==uuid.UUID(project)))
    db_session.commit()
    return project,settings,f'/api/v1/projects/{project}/embeddings'


def test_failed_later_batch_preserves_vectors_and_explicit_retry_only_embeds_remaining(client,db_session,configured,monkeypatch):
    project,settings,url=setup(client,db_session,monkeypatch)
    calls=[]
    def fake(_settings,texts):
        calls.extend(texts)
        if len(calls)==2:raise embeddings.EmbeddingError('EMBEDDING_PROVIDER_FAILED','Temporary failure')
        return [[1.]+[0.]*1023 for _ in texts]
    monkeypatch.setattr(embeddings,'embed_texts',fake)
    assert client.post(url+'/rebuild').status_code==503
    job=client.get(url+'/rebuild-status').json()
    assert job['status']=='failed'
    assert job['result']['updated_count']==1 and job['result']['remaining_count']==1
    assert job['result']['completed_batches']==1
    rows=list(db_session.scalars(select(KnowledgeEmbedding).where(KnowledgeEmbedding.project_id==uuid.UUID(project))))
    assert len(rows)==1
    first_id=rows[0].entity_id;first_hash=rows[0].content_sha256
    for _ in range(3):client.get(url+'/rebuild-status')
    assert len(calls)==2
    response=client.post(url+'/rebuild')
    assert response.status_code==200,response.text
    assert response.json()['updated_count']==1 and response.json()['reused_count']==1
    assert response.json()['remaining_count']==0 and len(calls)==3
    assert db_session.get(KnowledgeEmbedding,first_id).content_sha256==first_hash
    assert client.post(url+'/rebuild').json()['updated_count']==0
    assert len(calls)==3


def test_takeover_during_provider_call_rejects_late_batch_publication(client,db_session,configured,monkeypatch):
    project,settings,url=setup(client,db_session,monkeypatch)
    replacement=uuid.uuid4();calls=[]
    def fake(_settings,texts):
        calls.append(1)
        job=db_session.get(EmbeddingJob,uuid.UUID(project),populate_existing=True)
        job.execution_id=replacement;db_session.commit()
        return [[1.]+[0.]*1023 for _ in texts]
    monkeypatch.setattr(embeddings,'embed_texts',fake)
    response=client.post(url+'/rebuild')
    assert response.status_code==409
    assert response.json()['error']['code']=='EMBEDDING_REBUILD_REPLACED'
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEmbedding).where(KnowledgeEmbedding.project_id==uuid.UUID(project)))==0
    job=client.get(url+'/rebuild-status').json()
    assert job['id']==str(replacement) and job['status']=='running' and calls==[1]


def test_project_cannot_archive_while_a_live_index_job_is_running(client,db_session,configured,monkeypatch):
    project,settings,url=setup(client,db_session,monkeypatch)
    job=db_session.get(EmbeddingJob,uuid.UUID(project))
    job.status='running';job.lease_expires_at=utc_now()+timedelta(minutes=5);db_session.commit()
    project_read=client.get(f'/api/v1/projects/{project}').json()
    response=client.put(f'/api/v1/projects/{project}/archive',json={'archived':True,'expected_updated_at':project_read['updated_at']})
    assert response.status_code==409 and response.json()['error']['code']=='PROJECT_BUSY'
