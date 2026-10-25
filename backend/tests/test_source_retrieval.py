import json
from pathlib import Path

import pytest

from app.schemas.questions import AnswerDraft
from app.services import deepseek
from tests.test_graph import confirm
from tests.test_knowledge import configured

CASES = json.loads((Path(__file__).resolve().parents[2] / 'evaluation/regressions/source-location-v1/cases.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_independent_source_location_cases(client, db_session, configured, monkeypatch, case):
    project = client.post('/api/v1/projects', json={'name': 'Independent source cases'}).json()['id']
    quote = case['quote']
    if case['filename'].endswith('.java'):
        content = 'class Sample { Object save(Object value) { ' + quote + ' } }'
    elif case['filename'].endswith('.py'):
        content = 'def save(record):\n    ' + quote
    elif case['filename'].endswith('.ts'):
        content = 'function save(request: unknown) {\n    ' + quote + '\n}'
    else:
        content = '# ' + case['heading'] + '\n\n' + quote
    uploaded = client.post(f'/api/v1/projects/{project}/sources', files={'file': (case['filename'], content.encode(), 'text/plain')},
                           data={'relative_path':case['path']}).json()
    assert client.post(f"/api/v1/tasks/{uploaded['task_id']}/run").json()['status'] == 'succeeded'
    chunks = client.get(f"/api/v1/sources/{uploaded['source_id']}/chunks").json()['items']
    chunk = next(item for item in chunks if quote in item['content'])
    from app.schemas.knowledge import ExtractionDraft
    value = {'entities':[{'local_id':'operation','type':'CodeEntity','name':'Reviewed operation',
        'summary':'A reviewed implementation decision.','confidence':.8,
        'evidence':[{'chunk_id':chunk['id'],'quote':quote}]}], 'relations':[]}
    monkeypatch.setattr(deepseek, 'extract_candidates', lambda *_: ExtractionDraft.model_validate(value))
    assert client.post(f"/api/v1/sources/{uploaded['source_id']}/extract").json()['task']['status'] == 'succeeded'
    items = client.get(f'/api/v1/projects/{project}/reviews').json()['items']
    confirm(client, items[0])
    url = f'/api/v1/projects/{project}/search'
    before = client.get(url, params={'q': case['query'], 'mode': 'bm25'}).json()
    after = client.get(url, params={'q': case['query'], 'mode': 'bm25_source'}).json()
    assert after['lexical']['protocol'] == 'mixed-bm25-source-v1'
    assert bool(after['items']) == case.get('retrieval_match', case['answerable'])
    if case.get('retrieval_match', case['answerable']):
        assert after['items'][0]['evidence'][0]['chunk_id'] == items[0]['evidence'][0]['chunk_id']
        assert 'provenance' in after['items'][0]['matched_fields'] or case['id'] in {'direct', 'misleading-overlap'}
    if not case['answerable']:
        monkeypatch.setattr(deepseek, 'answer_question', lambda *_: AnswerDraft(supported=False, answer='证据不足。', confidence=0., citation_ids=[], missing_information=['缺少问题所述能力的证据']) if case.get('retrieval_match') else pytest.fail('No evidence must skip model'))
        response = client.post(f'/api/v1/projects/{project}/questions', json={'question': case['query'], 'retrieval_mode': 'bm25_source'})
        assert response.status_code == 200 and not response.json()['supported']
    assert client.get(url, params={'q': case['query'], 'mode': 'bm25'}).json() == before
