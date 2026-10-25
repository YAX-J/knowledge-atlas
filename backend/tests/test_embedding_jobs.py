import uuid
from datetime import timedelta


from app.api.routes import search as routes
from app.models.domain import utc_now
from app.models.embedding_job import EmbeddingJob
from app.services import embedding_jobs
from app.core.errors import AppError
from tests.test_knowledge import configured
from tests.test_questions import prepared_project


def test_rebuild_job_persists_result_and_prevents_duplicate_provider_calls(client, db_session, configured, monkeypatch):
    project, settings = prepared_project(client, monkeypatch)
    monkeypatch.setattr(routes, 'get_settings', lambda: settings)
    url = f'/api/v1/projects/{project}/embeddings'
    assert client.get(url + '/rebuild-status').json()['status'] == 'succeeded'
    calls = []
    def rebuild(db, **kwargs):
        calls.append(1)
        job = db.get(EmbeddingJob, uuid.UUID(project))
        assert job.status == 'running'
        assert client.post(url + '/rebuild').status_code == 409
        kwargs['checkpoint'](True)
        kwargs['checkpoint'](False)
        return dict(model='test', dimensions=1024, eligible_count=2, updated_count=0, reused_count=2)
    monkeypatch.setattr(embedding_jobs, 'rebuild_project_embeddings', rebuild)
    response = client.post(url + '/rebuild')
    assert response.status_code == 200, response.text
    job = client.get(url + '/rebuild-status').json()
    assert job['status'] == 'succeeded' and job['result'] == response.json() and len(calls) == 1
    other = client.post('/api/v1/projects', json={'name': 'Other'}).json()['id']
    assert client.get(f'/api/v1/projects/{other}/embeddings/rebuild-status').json() is None


def test_interrupted_job_requires_explicit_retry_and_fences_old_execution(client, db_session, configured, monkeypatch):
    project, settings = prepared_project(client, monkeypatch)
    monkeypatch.setattr(routes, 'get_settings', lambda: settings)
    now = utc_now()
    job = db_session.get(EmbeddingJob, uuid.UUID(project))
    job.status, job.started_at, job.lease_expires_at = 'running', now - timedelta(hours=1), now - timedelta(seconds=1)
    db_session.commit()
    url = f'/api/v1/projects/{project}/embeddings'
    assert client.get(url + '/rebuild-status').json()['interrupted']
    assert client.post(url + '/rebuild').json()['error']['code'] == 'EMBEDDING_REBUILD_INTERRUPTED'
    assert client.post(url + '/rebuild?retry_interrupted=true').status_code == 200
    assert client.get(url + '/rebuild-status').json()['status'] == 'succeeded'


def test_failed_rebuild_persists_sanitized_failure_and_allows_explicit_new_request(client, db_session, configured, monkeypatch):
    project, settings = prepared_project(client, monkeypatch)
    monkeypatch.setattr(routes, 'get_settings', lambda: settings)
    def fail(*_, **kwargs):
        raise AppError(status_code=503, code='EMBEDDING_PROVIDER_FAILED', message='暂不可用')
    monkeypatch.setattr(embedding_jobs, 'rebuild_project_embeddings', fail)
    url = f'/api/v1/projects/{project}/embeddings'
    assert client.post(url + '/rebuild').status_code == 503
    job = client.get(url + '/rebuild-status').json()
    assert job['status'] == 'failed' and job['error']['code'] == 'EMBEDDING_PROVIDER_FAILED'


def test_replaced_job_cannot_finish_or_overwrite_new_owner(client, db_session, configured, monkeypatch):
    project, settings = prepared_project(client, monkeypatch)
    replacement = uuid.uuid4()
    def replace(db, **kwargs):
        job = db.get(EmbeddingJob, uuid.UUID(project))
        job.execution_id = replacement
        db.commit()
        kwargs['checkpoint'](False)
    monkeypatch.setattr(embedding_jobs, 'rebuild_project_embeddings', replace)
    url = f'/api/v1/projects/{project}/embeddings'
    assert client.post(url + '/rebuild').json()['error']['code'] == 'EMBEDDING_REBUILD_REPLACED'
    job = client.get(url + '/rebuild-status').json()
    assert job['id'] == str(replacement) and job['status'] == 'running'
