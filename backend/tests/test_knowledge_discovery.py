import uuid

import pytest

from app.api.dependencies import get_current_user_id
from app.main import app
from app.schemas.questions import AnswerDraft
from app.services import deepseek
from tests.test_evolution import reviewed_decision
from tests.test_graph import confirm, extracted
from tests.test_knowledge import configured
from tests.test_questions import prepared_project
from tests.test_sources import create_project


def test_review_filters_combine_literal_text_kind_status_and_pagination(client, configured, monkeypatch):
    def rename(draft):
        draft['entities'][0]['name'] = '保存_100%中文资料'
        return draft
    project, source, items = extracted(client, monkeypatch, rename)
    entity = next(item for item in items if item['name'] == '保存_100%中文资料')
    confirm(client, entity)
    monkeypatch.setattr(deepseek, 'extract_candidates', lambda *_: pytest.fail('Listing must not call a model'))
    url = f'/api/v1/projects/{project}/reviews'
    params = {'source_id': source['source_id'], 'kind': 'entity', 'review_status': 'confirmed', 'q': '_100%', 'page_size': 1}
    data = client.get(url, params=params).json()
    assert data['total'] == 1 and data['items'][0]['id'] == entity['id']
    assert client.get(url, params={**params, 'page': 2}).json()['items'] == []
    assert client.get(url, params={**params, 'review_status': 'pending'}).json()['total'] == 0
    assert client.get(url, params={'source_id': source['source_id'], 'kind': 'relation'}).json()['total'] == 1
    assert client.get(url, params={'source_id': source['source_id'], 'q': '中文', 'kind': 'entity'}).json()['total'] == 1
    assert client.get(url, params={'source_id': source['source_id'], 'q': '中文'}).json()['total'] == 2  # Derived relation name also contains the endpoint name.
    assert client.get(url, params={'source_id': source['source_id'], 'q': "' OR 1=1 --"}).json()['total'] == 0
    status = client.get(f"/api/v1/sources/{source['source_id']}/extraction").json()
    assert status['candidate_count'] == 3 and status['review_counts']['confirmed'] == 1
    assert client.get(url, params={'kind': 'invalid'}).status_code == 422
    assert client.get(url, params={'q': 'x'*201}).status_code == 422


def test_review_discovery_preserves_source_project_user_boundaries(client, configured, monkeypatch):
    project, source, _ = extracted(client, monkeypatch)
    other, other_source, _ = extracted(client, monkeypatch)
    url = f'/api/v1/projects/{project}/reviews'
    assert client.get(url, params={'source_id': other_source['source_id'], 'q': 'PostgreSQL'}).status_code == 404
    response = client.get(f'/api/v1/projects/{other}/reviews', params={'source_id': source['source_id']})
    assert response.status_code == 404
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(url, params={'q': 'PostgreSQL', 'kind': 'entity'}).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)


def test_governance_filters_before_result_limit_and_reports_scan_counts(client, configured, monkeypatch):
    project = create_project(client)
    reviewed_decision(client, monkeypatch, project, 1, summary='First')
    reviewed_decision(client, monkeypatch, project, 2, summary='Second')
    reviewed_decision(client, monkeypatch, project, 3, summary='Second')
    url = f'/api/v1/projects/{project}/governance'
    all_findings = client.get(url).json()
    assert all_findings['counts_by_kind'] == {'missing_evidence': 0, 'duplicate': 1, 'possible_conflict': 1, 'orphan': 3}
    duplicate = client.get(url, params={'kind': 'duplicate', 'limit': 1}).json()
    assert duplicate['kind_filter'] == 'duplicate' and not duplicate['truncated']
    assert len(duplicate['findings']) == 1 and duplicate['findings'][0]['kind'] == 'duplicate'
    orphans = client.get(url, params={'kind': 'orphan', 'limit': 1}).json()
    assert orphans['truncated'] and orphans['findings'][0]['kind'] == 'orphan'
    assert orphans['counts_by_kind'] == all_findings['counts_by_kind']
    assert client.get(url, params={'kind': 'invalid'}).status_code == 422
    empty = create_project(client)
    assert not client.get(f'/api/v1/projects/{empty}/governance', params={'kind': 'duplicate'}).json()['findings']


def test_deduplicated_question_evidence_retains_all_entity_attributions(client, configured, monkeypatch):
    project, _ = prepared_project(client, monkeypatch)
    payloads = []
    def answer(_settings, _question, evidence):
        assert len(evidence) == 1
        assert set(evidence[0]['entity_names']) == {'PostgreSQL', 'Store knowledge'}
        payloads.append(evidence)
        return AnswerDraft(supported=True, answer='Use PostgreSQL.', confidence=.8,
                           citation_ids=[evidence[0]['id']], missing_information=[])
    monkeypatch.setattr(deepseek, 'answer_question', answer)
    response = client.post(f'/api/v1/projects/{project}/questions', json={
        'question': 'PostgreSQL storage', 'retrieval_mode': 'bm25'})
    assert response.status_code == 200, response.text
    data = response.json()
    evidence = data['evidence'][0]
    assert evidence['id'] == payloads[0][0]['id']
    assert len(evidence['related_entities']) == 2
    assert {entity['name'] for entity in evidence['related_entities']} == {'PostgreSQL', 'Store knowledge'}
    assert evidence['entity_id'] == evidence['related_entities'][0]['id']
    assert data['retrieval']['duplicate_evidence_count'] == 1
