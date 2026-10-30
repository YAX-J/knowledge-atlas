import json

from sqlalchemy import inspect

from app.services import agent_workflows as workflows
from tests.test_agent_list_performance import NOW, USER, scope, run, selects


def test_summary_avoids_heavy_columns_and_preserves_full_detail(client,db_session):
    context=scope(db_session)
    project_id=context[0].id
    records=[run(db_session,context,result={'answer':{'answer':'synthetic '*400}},
        events=[dict(sequence=i+1,agent='workflow',kind='synthetic',status='saved',elapsed_ms=i) for i in range(128)]) for _ in range(10)]
    ids=[record.id for record in records]
    db_session.commit();db_session.expunge_all()
    with selects(db_session) as statements:
        summary=workflows.list_runs(db_session,user_id=USER,project_id=project_id,page=1,page_size=10,summary=True)
    assert len(statements)==3
    page_sql=next(sql for sql in statements if sql.startswith('SELECT agent_runs.id'))
    for name in ('request','result','events','usage','input_sha256'):
        assert f'agent_runs.{name}' not in page_sql
    from app.models.agent_run import AgentRun
    loaded=[item for item in db_session.identity_map.values() if isinstance(item,AgentRun)]
    for item in loaded:assert {'request','result','events','usage'}.issubset(inspect(item).unloaded)
    full=workflows.list_runs(db_session,user_id=USER,project_id=project_id,page=1,page_size=10)
    assert [item.id for item in summary.items]==[item.id for item in full.items]
    assert len(summary.model_dump_json().encode())*10 < len(full.model_dump_json().encode())
    base=f'/api/v1/projects/{project_id}/agent-runs'
    response=client.get(base+'?summary=true')
    assert response.status_code==200,response.text
    expected={'id','project_id','source_id','kind','status','error_code','created_at','updated_at'}
    assert set(response.json()['items'][0])==expected
    detail=client.get(base+f'/{ids[0]}').json()
    assert len(detail['events'])==128 and 'synthetic' in json.dumps(detail['result'])
    assert client.get(base).json()['items'][0].keys()==detail.keys()


def test_summary_expiry_and_empty_pagination(client,db_session,monkeypatch):
    monkeypatch.setattr(workflows,'utc_now',lambda:NOW)
    context=scope(db_session)
    project_id=context[0].id
    run(db_session,context,status='running',lease_until=NOW)
    db_session.commit()
    base=f'/api/v1/projects/{project_id}/agent-runs'
    assert client.get(base+'?summary=true').json()['items'][0]['status']=='interrupted'
    page=client.get(base+'?summary=true&page=2').json()
    assert page['items']==[] and page['total']==1
