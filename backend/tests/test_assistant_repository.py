import json

import httpx
from sqlalchemy import func, select

from app.api.routes import assistant as routes
from app.core.config import Settings
from app.llm.providers import deepseek
from app.models.domain import ProcessingTask, RepositorySnapshot
from app.models.graph import KnowledgeEntity
from tests.test_assistant_execution import continuation
from tests.test_assistant_workspace import process
from tests.test_github_import import install_github_mock, register_github
from tests.test_multi_agent import tool
from tests.test_project_assistant import endpoint, finish, request
from tests.test_sources import create_project


def test_repository_job_resumes_fixed_commit_then_parses_and_cites(client, db_session, monkeypatch):
    project = create_project(client)
    repo = register_github(client, project)
    first_commit = 'a' * 40
    branch_commit = first_commit
    blocked = True
    downloads = []

    def provider(call):
        path = call.url.path
        if path == '/repos/example/demo':
            return httpx.Response(200, json={'default_branch': 'main', 'id': 42})
        if '/commits/' in path:
            ref = path.rsplit('/', 1)[-1]
            commit = branch_commit if ref == 'main' else ref
            return httpx.Response(200, json={'sha': commit, 'commit': {'tree': {'sha': 't' * 40}}})
        if '/trees/' in path:
            return httpx.Response(200, json={'tree': [
                {'type': 'blob', 'path': 'README.md', 'sha': 'readme', 'size': 42},
                {'type': 'blob', 'path': 'src/storage.py', 'sha': 'storage', 'size': 42},
                {'type': 'blob', 'path': 'src/extra.py', 'sha': 'extra', 'size': 42},
            ]})
        blob = path.rsplit('/', 1)[-1]
        if blocked and blob == 'extra':
            return httpx.Response(429)
        downloads.append(blob)
        return httpx.Response(200, content={
            'readme': b'# Architecture\n\nPostgreSQL stores the data.\n',
            'storage': b'def storage():\n    return "PostgreSQL"\n',
            'extra': b'def extra():\n    return 1\n',
        }[blob])

    install_github_mock(monkeypatch, provider)
    settings = Settings(_env_file=None, github_api_base_url='https://api.github.test', github_import_max_files=1,
                        deepseek_api_key='local-substitute')
    monkeypatch.setattr(routes, 'get_settings', lambda: settings)
    calls = []

    def report(_settings, messages, definitions, **_kwargs):
        calls.append(1)
        assert all(tool['function']['name'] != 'import_repository_snapshot' for tool in definitions)
        if len(calls) == 1:
            scope = json.loads(messages[1]['content'])['scope']['repository_progress']
            assert scope['parsed_files'] == 3 and scope['commit_sha'] == first_commit
            return tool('search_sources', {'query': 'PostgreSQL'})
        return finish(json.loads(messages[-1]['content'])['references'])

    monkeypatch.setattr(deepseek, 'call_agent_turn', report)
    body = request(protocol='assistant-task-v3', whole_repository=True, repository_id=repo['id'], repository_ref='main',
                   allowed_actions=['import_repository_snapshot'])
    submitted = client.post(endpoint(project), json=body)
    assert submitted.status_code == 202, submitted.text
    url = endpoint(project) + '/' + submitted.json()['id']
    assert not downloads and not calls

    first = process(db_session, settings)
    assert first['status'] == 'queued' and first['scope']['repository_progress']['completed_files'] == 1
    partial = process(db_session, settings)
    assert partial['status'] == 'failed' and partial['error_code'] == 'GITHUB_RATE_LIMITED', partial
    assert partial['scope']['repository_progress']['completed_files'] == 1
    assert partial['scope']['repository_progress']['commit_sha'] == first_commit
    assert partial['can_continue'] and partial['usage']['model'] == 0
    assert client.get(url).json() == partial
    assert downloads == ['readme'] and not calls

    blocked = False
    branch_commit = 'b' * 40
    assert client.post(url + '/continue', json=continuation(partial)).status_code == 202
    second = process(db_session, settings)
    assert second['status'] == 'queued' and second['scope']['repository_progress']['completed_files'] == 2
    done = process(db_session, settings)
    assert done['status'] == 'succeeded', done
    progress = done['scope']['repository_progress']
    assert progress['phase'] == 'reporting' and progress['parsed_files'] == progress['total_files'] == 3
    assert progress['failed_files'] == progress['skipped_files'] == 0
    assert len(downloads) == 3 and len(calls) == 2
    assert done['usage']['tool'] == 1
    references = done['result']['references']
    assert references and all(ref['commit_sha'] == first_commit and ref['snapshot_id'] == progress['snapshot_id'] for ref in references)
    assert all(ref['chunk_id'] and 'PostgreSQL' in ref['quote'] for ref in references)
    assert db_session.scalar(select(func.count()).select_from(ProcessingTask).where(ProcessingTask.status == 'succeeded')) == 3
    assert db_session.scalar(select(func.count()).select_from(RepositorySnapshot)) == 3
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEntity)) == 0
    assert client.post(endpoint(project), json=body).json() == done
    assert len(calls) == 2
