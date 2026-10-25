import uuid

from sqlalchemy import select

from app.api.dependencies import get_current_user_id
from app.main import app
from app.models.domain import ProcessingTask, Project, SourceDocument, SourceStatus, utc_now
from app.services.source_languages import SOURCE_TYPE_BY_SUFFIX
from tests.test_sources import create_project


def upload(client, project, name, content, path=None):
    response = client.post(f'/api/v1/projects/{project}/sources',
                           files={'file': (name, content.encode(), 'text/plain')},
                           data={'relative_path': path} if path else {})
    assert response.status_code == 202, response.text
    return response.json()


def test_source_filters_combine_literal_name_path_type_status_and_pagination(client, db_session):
    project = create_project(client)
    first = upload(client, project, '中文_100%.md', '# First', 'notes/中文_100%.md')
    second = upload(client, project, 'SECOND.MD', '# Second', 'notes/中文/SECOND.MD')
    upload(client, project, 'main.py', 'print("notes")', 'notes/main.py')
    record = db_session.get(SourceDocument, uuid.UUID(second['source_id']))
    record.status = SourceStatus.FAILED
    db_session.commit()
    url = f'/api/v1/projects/{project}/sources'
    params = {'q': ' notes/ ', 'source_type': 'markdown', 'page_size': 1}
    page = client.get(url, params=params).json()
    assert page['total'] == 2 and len(page['items']) == 1
    later = client.get(url, params={**params, 'page': 2}).json()
    assert later['total'] == 2 and page['items'][0]['id'] != later['items'][0]['id']
    assert client.get(url, params={**params, 'source_status': 'failed'}).json()['items'][0]['id'] == second['source_id']
    assert client.get(url, params={'q': '_100%'}).json()['total'] == 1
    assert client.get(url, params={'q': '_100%'}).json()['items'][0]['id'] == first['source_id']
    assert client.get(url, params={'q': 'second.md'}).json()['total'] == 1
    assert client.get(url, params={'q': '中文'}).json()['total'] == 2
    assert client.get(url, params={'q': "' OR 1=1 --"}).json()['total'] == 0
    assert client.get(url, params={'q': 'does not exist'}).json()['total'] == 0


def test_source_filters_support_every_registered_language(client):
    project = create_project(client)
    for index, source_type in enumerate(sorted(set(SOURCE_TYPE_BY_SUFFIX.values()))):
        suffix = next(suffix for suffix, value in SOURCE_TYPE_BY_SUFFIX.items() if value == source_type)
        uploaded = upload(client, project, f'file{suffix}', f'// synthetic fixture {index}')
        data = client.get(f'/api/v1/projects/{project}/sources', params={'source_type': source_type}).json()
        assert data['total'] == 1 and data['items'][0]['id'] == uploaded['source_id']


def test_source_filters_preserve_user_project_and_archive_boundaries(client, db_session):
    first, second = create_project(client), create_project(client)
    expected = upload(client, first, 'same.md', '# First')
    upload(client, second, 'same.md', '# Second')
    url = f'/api/v1/projects/{first}/sources'
    data = client.get(url, params={'q': 'same', 'source_type': 'markdown'}).json()
    assert data['total'] == 1 and data['items'][0]['id'] == expected['source_id']
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(url, params={'q': 'same'}).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)
    db_session.get(Project, uuid.UUID(first)).archived_at = utc_now()
    db_session.commit()
    assert client.get(url, params={'source_status': 'uploaded'}).status_code == 404


def test_source_filter_validation_and_unfiltered_default(client):
    project = create_project(client)
    upload(client, project, 'first.md', '# First')
    url = f'/api/v1/projects/{project}/sources'
    baseline = client.get(url).json()
    assert client.get(url, params={'q': '  '}).json() == baseline
    for params in ({'source_type': 'unknown'}, {'source_status': 'succeeded'}, {'q': 'x' * 201}):
        assert client.get(url, params=params).status_code == 422


def test_source_filter_listing_is_read_only_and_preserves_parsing_task_link(client, db_session):
    project = create_project(client)
    uploaded = upload(client, project, 'first.md', '# First')
    before = [(item.id, item.status, item.updated_at) for item in db_session.scalars(select(ProcessingTask))]
    data = client.get(f'/api/v1/projects/{project}/sources', params={'q': 'first', 'source_status': 'uploaded'}).json()
    assert data['items'][0]['task_id'] == uploaded['task_id']
    assert data['items'][0]['task_status'] == 'queued'
    assert before == [(item.id, item.status, item.updated_at) for item in db_session.scalars(select(ProcessingTask))]
