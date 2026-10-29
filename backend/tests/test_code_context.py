import uuid
from datetime import timedelta
from app.models.domain import RepositorySnapshot,RepositorySnapshotFile,SourceDocument,utc_now
from app.services import code_semantics
from tests.test_code_agent import _code,_repository
from tests.test_sources import create_project


def prepare(client,monkeypatch):
    project=create_project(client);repository=_repository(client,project)
    old=_code(client,project,repository,'helper.ts','export function help() {return 1;}\n')
    new=_code(client,project,repository,'helper.ts','export function help() {return 2;}\n')
    main=_code(client,project,repository,'main.ts','import {help} from "./helper";\nhelp();\n')
    captured=[]
    def analyze(source,related):
        captured.append((source,related))
        return dict(engine='test-static-context',calls=[],diagnostics=[],truncated=False)
    monkeypatch.setattr(code_semantics,'analyze',analyze)
    return project,repository,old,new,main,captured


def test_local_latest_and_explicit_versions_do_not_mix_repeated_paths(client,db_session,monkeypatch):
    project,repository,old,new,main,captured=prepare(client,monkeypatch)
    endpoint=f"/api/v1/sources/{main['source_id']}"
    contexts=client.get(endpoint+'/analysis-contexts').json()
    assert contexts['version_groups'][0]['path']=='helper.ts'
    assert contexts['version_groups'][0]['versions'][0]['id']==new['source_id']
    for identifier in (None,old['source_id'],new['source_id']):
        query={'strategy':'semantic'}
        if identifier:query['version_ids']=identifier
        result=client.post(endpoint+'/agent-call-analysis',params=query)
        assert result.status_code==200,result.text
        assert len(captured[-1][1])==1
        assert str(captured[-1][1][0].id)==(identifier or new['source_id'])
    count=len(captured)
    assert client.post(endpoint+'/agent-call-analysis',params={'strategy':'semantic','version_ids':str(uuid.uuid4())}).status_code==404
    assert len(captured)==count
    db_session.get(SourceDocument,uuid.UUID(main['source_id'])).status='uploaded'
    db_session.commit()
    unavailable=client.get(endpoint+'/analysis-contexts')
    assert unavailable.status_code==409 and unavailable.json()['error']['code']=='CALL_AGENT_SOURCE_NOT_READY'


def test_explicit_commit_pins_paths_versions_and_scope(client,db_session,monkeypatch):
    project,repository,old,new,main,captured=prepare(client,monkeypatch)
    stored=db_session.get(SourceDocument,uuid.UUID(main['source_id']))
    snapshots=[]
    for number,helper in enumerate((old,new)):
        snapshot=RepositorySnapshot(user_id=stored.user_id,project_id=stored.project_id,repository_id=uuid.UUID(repository),
            provider='github',ref='main',commit_sha=str(number+1)*40,tree_sha=str(number+3)*40,
            created_at=utc_now()+timedelta(seconds=number))
        db_session.add(snapshot);db_session.flush()
        for path,document in [('main.ts',main),('helper.ts',helper)]:
            db_session.add(RepositorySnapshotFile(snapshot_id=snapshot.id,path=path,source_id=uuid.UUID(document['source_id']),
                blob_sha=path+str(number),size_bytes=10,status='imported'))
        snapshots.append(snapshot.id)
    # A later rename cannot rewrite the earlier commit's analysis paths.
    db_session.get(SourceDocument,uuid.UUID(old['source_id'])).relative_path='renamed.ts'
    db_session.commit()
    endpoint=f"/api/v1/sources/{main['source_id']}"
    contexts=client.get(endpoint+'/analysis-contexts').json()
    assert contexts['default_snapshot_id']==str(snapshots[1])
    for snapshot_id,helper in zip(snapshots,(old,new)):
        result=client.post(endpoint+'/agent-call-analysis',params={'strategy':'semantic','snapshot_id':str(snapshot_id)})
        assert result.status_code==200,result.text
        assert result.json()['context']['snapshot_id']==str(snapshot_id)
        assert str(captured[-1][1][0].id)==helper['source_id']
        assert captured[-1][1][0].relative_path=='helper.ts'
    result=client.post(endpoint+'/agent-call-analysis',params={'strategy':'semantic'})
    assert result.status_code==200 and str(captured[-1][1][0].id)==new['source_id']
    other=create_project(client);other_repo=_repository(client,other)
    foreign=_code(client,other,other_repo,'main.ts','function run() {}\n')
    assert client.post(f"/api/v1/sources/{foreign['source_id']}/agent-call-analysis",
        params={'strategy':'semantic','snapshot_id':str(snapshots[0])}).status_code==404
    assert client.post(endpoint+'/agent-call-analysis',params={'strategy':'semantic','snapshot_id':str(snapshots[0]),
        'version_ids':old['source_id']}).status_code==409
    # Snapshot metadata is inspected before bounded body loading. An unready related
    # file is explicitly partial, while an oversized ready body must never load.
    from sqlalchemy import event
    from app.services.code_context import select_context
    helper=db_session.get(SourceDocument,uuid.UUID(new['source_id']))
    helper.status='uploaded'
    db_session.commit()
    _main, related, truncated, _context=select_context(db_session,stored,{'typescript'},snapshot_id=snapshots[1])
    assert not related and truncated
    helper.status='ready';helper.size_bytes=30*1024*1024
    db_session.commit()
    loaded=[]
    def capture(_connection,_cursor,statement,*_args):
        if 'source_documents.content,' in statement:loaded.append(statement)
    # Resolve source attributes before measuring; the selector already receives this body.
    assert stored.id
    event.listen(db_session.get_bind(),'before_cursor_execute',capture)
    try:
        _main, related, truncated, _context=select_context(db_session,stored,{'typescript'},snapshot_id=snapshots[1])
    finally:
        event.remove(db_session.get_bind(),'before_cursor_execute',capture)
    assert not related and truncated and not loaded
