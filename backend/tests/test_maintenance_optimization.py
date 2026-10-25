from tests.test_evolution import reviewed_decision
from tests.test_graph import confirm, extracted
from tests.test_knowledge import configured
from tests.test_sources import create_project


def test_review_totals_cover_source_and_update_after_each_action(client, configured, monkeypatch):
    project, source, items = extracted(client, monkeypatch)
    url = f"/api/v1/sources/{source['source_id']}/extraction"
    assert client.get(url).json()['review_counts'] == {'pending': 3, 'confirmed': 0, 'rejected': 0}
    entities = [item for item in items if item['kind'] == 'entity']
    confirm(client, entities[0])
    assert client.post(f"/api/v1/reviews/{entities[1]['id']}/resolve", json={'action': 'reject'}).status_code == 200
    status = client.get(url).json()
    assert status['candidate_count'] == 3
    assert status['review_counts'] == {'pending': 1, 'confirmed': 1, 'rejected': 1}
    _, another, _ = extracted(client, monkeypatch)
    assert client.get(f"/api/v1/sources/{another['source_id']}/extraction").json()['review_counts']['pending'] == 3
    assert client.get(url).json() == status


def test_duplicate_in_later_summary_group_is_found_before_orphans(client, configured, monkeypatch):
    project = create_project(client)
    first = reviewed_decision(client, monkeypatch, project, 1, summary='First conclusion')
    second = reviewed_decision(client, monkeypatch, project, 2, summary='Another conclusion')
    third = reviewed_decision(client, monkeypatch, project, 3, summary='Another conclusion')
    url = f'/api/v1/projects/{project}/governance'
    result = client.get(url).json()
    duplicate = next(item for item in result['findings'] if item['kind'] == 'duplicate')
    assert duplicate['entity_ids'] == [second['entity']['id'], third['entity']['id']]
    assert [item['summary'] for item in duplicate['entities']] == ['Another conclusion'] * 2
    limited = client.get(url, params={'limit': 1}).json()
    assert limited['findings'] == [duplicate] and limited['truncated']
    assert client.get(url).json()['findings'] == result['findings']
    assert client.get(f"/api/v1/knowledge/entities/{first['entity']['id']}").json() == first
