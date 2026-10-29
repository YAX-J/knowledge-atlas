"""Persisted API workflow; providers are explicitly synthetic, never quality scores."""
import uuid
from app.api.routes import conversations as routes
from app.schemas.questions import AnswerDraft
from app.services import deepseek
from tests.test_questions import prepared_project
from tests.test_knowledge import configured


def test_uploaded_reviewed_graph_and_conversation_survive_new_reads(client, configured, monkeypatch):
    project,settings=prepared_project(client,monkeypatch)
    monkeypatch.setattr(routes,'get_settings',lambda:settings)
    monkeypatch.setattr(deepseek,'answer_question',lambda _s,_q,evidence,**_kw:AnswerDraft(
        supported=True,answer='PostgreSQL stores knowledge.',confidence=.9,
        citation_ids=[evidence[0]['id']],missing_information=[]))
    base=f'/api/v1/projects/{project}'
    graph=client.get(base+'/graph')
    assert graph.status_code==200 and len(graph.json()['nodes'])==2 and len(graph.json()['edges'])==1
    assert client.get(base+'/search',params={'q':'PostgreSQL','mode':'bm25'}).json()['items']
    conversation=client.post(base+'/conversations',json={}).json()
    path=base+f"/conversations/{conversation['id']}/turns"
    body=dict(request_id=str(uuid.uuid4()),question='Which database stores knowledge?',retrieval_mode='rrf')
    answered=client.post(path,json=body)
    assert answered.status_code==200 and answered.json()['answer']['supported']
    assert client.get(path).json()['items'][0]['answer']==answered.json()['answer']
    assert client.post(path,json=body).json()==answered.json()
    evidence=answered.json()['answer']['evidence'][0]
    original=client.get(base+f"/sources/{evidence['source_id']}/chunks/{evidence['chunk_id']}")
    assert original.status_code==200 and evidence['quote'] in original.json()['content']
