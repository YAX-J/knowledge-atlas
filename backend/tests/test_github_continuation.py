import httpx
import hashlib
from app.models.domain import utc_now
from tests.test_github_import import create_project, register_github, install_github_mock


def test_continue_large_repository_pins_commit_and_carries_complete_provenance(client, monkeypatch):
    requested=[]
    revision='a'
    def respond(request):
        path=request.url.path
        requested.append(path)
        if path=='/repos/example/demo':
            return httpx.Response(200,json={'default_branch':'main','private':True})
        if '/commits/' in path:
            ref=path.rsplit('/',1)[-1]
            commit=ref[0] if ref in {'a'*40,'b'*40} else revision
            return httpx.Response(200,json={'sha':commit*40,'commit':{'tree':{'sha':('t' if commit=='a' else 'u')*40}}})
        if '/git/trees/' in path:
            entries=[dict(path=f'docs/{i:03}.md',type='blob',sha=str(i),size=10) for i in range(75)]
            if path.endswith('u'*40):
                entries=entries[2:]+[dict(path='docs/renamed.md',type='blob',sha='0',size=10)]
            return httpx.Response(200,json={'truncated':False,'tree':[
                *entries]})
        return httpx.Response(200,content=f'# File {path.rsplit("/",1)[-1]}'.encode())
    install_github_mock(monkeypatch,respond,token='private-test-token')
    project=create_project(client)
    repo=register_github(client,project)
    base=f"/api/v1/projects/{project}/repositories/{repo['id']}"
    first=client.post(base+'/sync-github',json={})
    assert first.status_code==200,first.text
    first=first.json()
    assert first['completed_files']==50 and first['remaining_files']==25
    revision='b'  # The branch moves while continuation must stay on commit a.
    second=client.post(base+'/sync-github',json={'continue_from_snapshot':first['continuation_snapshot_id']})
    assert second.status_code==200,second.text
    second=second.json()
    assert second['completed_files']==75 and second['remaining_files']==0
    assert second['continuation_snapshot_id'] is None and not second['truncated']
    assert second['access']=='private'
    assert f"/repos/example/demo/commits/{'a'*40}" in requested
    saved=client.get(base+f"/snapshots/{second['snapshot_id']}/files",params={'page_size':100}).json()
    assert saved['total']==75
    assert all(item['source_id'] for item in saved['items'])
    assert sum('/git/blobs/' in path for path in requested)==75
    other=create_project(client)
    other_repo=register_github(client,other)
    assert client.post(f"/api/v1/projects/{other}/repositories/{other_repo['id']}/sync-github",
        json={'continue_from_snapshot':first['snapshot_id']}).status_code==404
    next_page=client.post(base+'/sync-github',json={}).json()
    assert next_page['commit_sha']=='b'*40 and not next_page['deletion_detection_complete']
    final=client.post(base+'/sync-github',json={'continue_from_snapshot':next_page['snapshot_id']})
    assert final.status_code==200,final.text
    final=final.json()
    assert final['deletion_detection_complete'] and final['deleted_count']==1 and final['renamed_count']==1
    assert any(item['path']=='docs/001.md' and item['status']=='deleted' for item in final['items'])
    assert any(item['path']=='docs/renamed.md' and item['previous_path']=='docs/000.md' for item in final['items'])
    assert sum('/git/blobs/' in path for path in requested)==75  # Blob reuse spans all pages.


def test_truncated_recursive_tree_resumes_directory_frontier_without_changing_old_snapshot(client,db_session,monkeypatch):
    import uuid
    from app.models.domain import RepositorySnapshot
    def respond(request):
        path=request.url.path
        if path=='/repos/example/demo':return httpx.Response(200,json={'default_branch':'main'})
        if '/commits/' in path:return httpx.Response(200,json={'sha':'a'*40,'commit':{'tree':{'sha':'root'}}})
        if path.endswith('/git/trees/root'):
            if 'recursive' in request.url.params:return httpx.Response(200,json={'truncated':True,'tree':[]})
            return httpx.Response(200,json={'truncated':False,'tree':[dict(path=f'd{i}',sha=f't{i}',type='tree') for i in range(12)]})
        if '/git/trees/t' in path:
            number=path.rsplit('t',1)[-1]
            return httpx.Response(200,json={'truncated':False,'tree':[dict(path='note.md',sha='b'+number,size=10,type='blob')]})
        return httpx.Response(200,content=('# '+path.rsplit('/',1)[-1]).encode())
    install_github_mock(monkeypatch,respond)
    project=create_project(client);repository=register_github(client,project)
    endpoint=f"/api/v1/projects/{project}/repositories/{repository['id']}/sync-github"
    first=client.post(endpoint,json={})
    assert first.status_code==200,first.text
    first=first.json()
    assert first['pending_directories']==3 and not first['tree_complete'] and first['completed_files']==9
    second=client.post(endpoint,json={'continue_from_snapshot':first['snapshot_id']})
    assert second.status_code==200,second.text
    second=second.json()
    assert second['tree_complete'] and second['completed_files']==12 and not second['truncated']
    old=db_session.get(RepositorySnapshot,uuid.UUID(first['snapshot_id']))
    assert len(old.scan_state['entries'])==9 and len(old.scan_state['frontier'])==3


def test_directory_limits_and_single_tree_truncation_never_claim_complete(monkeypatch):
    from app.services import github_tree
    monkeypatch.setattr(github_tree,'MAX_MANIFEST_FILES',2)
    previous=dict(entries=[],frontier=[dict(path='',sha='root')],complete=False,blocked=False)
    for payload in (
        dict(truncated=True,tree=[]),
        dict(truncated=False,tree=[dict(path=f'{i}.md',type='blob',sha=str(i),size=2) for i in range(3)]),
        dict(truncated=False,tree=[dict(path=str(i),type='tree',sha=str(i)) for i in range(3)]),
    ):
        state=github_tree.manifest(None,base='https://example.test',tree_sha='root',previous=previous,
            get_json=lambda *_a,**_k:payload,supported=lambda values:[item for item in values if item['type']=='blob'])
        assert state['blocked'] and not state['complete'] and len(state['entries'])<=2
        assert previous['frontier']==[dict(path='',sha='root')] and not previous['blocked']


def test_whole_repo_resumes_saved_same_commit_and_uses_verified_raw_content(client, monkeypatch):
    from app.api.routes import repositories
    from app.core.config import Settings
    from app.services import github_import

    files = {f"docs/{index}.md": f"# File {index}".encode() for index in range(3)}
    blobs = {hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest(): content
             for content in files.values()}
    manifest = [dict(path=path, type="blob", sha=sha, size=len(content))
                for path, (sha, content) in zip(files, blobs.items(), strict=True)]
    requests = []

    def respond(request):
        requests.append(request)
        path = request.url.path
        if request.url.host == "raw.githubusercontent.com":
            assert "authorization" not in request.headers
            assert path.startswith(f"/example/demo/{'a' * 40}/")
            return httpx.Response(200, content=files[path.split("/", 4)[-1]])
        if path == "/repos/example/demo":
            return httpx.Response(200, json={"default_branch": "main", "private": False, "id": 42})
        if "/commits/" in path:
            return httpx.Response(200, json={"sha": "a" * 40, "commit": {"tree": {"sha": "tree"}}})
        if "/trees/" in path:
            return httpx.Response(200, json={"tree": manifest})
        return httpx.Response(200, content=blobs[path.rsplit("/", 1)[-1]])

    original_client = httpx.Client
    monkeypatch.setattr(github_import.httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    monkeypatch.setattr(repositories, "get_settings", lambda: Settings(_env_file=None, github_token=None, github_import_max_files=1))
    project = create_project(client)
    repo = register_github(client, project)
    url = f"/api/v1/projects/{project}/repositories/{repo['id']}/sync-github"

    def sync(payload):
        result = client.post(url, json=payload)
        assert result.status_code == 200, result.text
        return result.json()

    first = sync({})
    second = sync({"resume_incomplete": True})
    third = sync({"resume_incomplete": True, "continue_from_snapshot": second["snapshot_id"]})
    assert (first["completed_files"], second["completed_files"], third["completed_files"]) == (1, 2, 3)
    assert third["remaining_files"] == 0 and not third["truncated"]
    assert sum("/git/trees/" in request.url.path for request in requests) == 1
    assert sum(request.url.path == "/repos/example/demo" for request in requests) == 2
    assert sum("/commits/" in request.url.path for request in requests) == 2
    assert sum("/git/blobs/" in request.url.path for request in requests) == 1
    assert sum(request.url.host == "raw.githubusercontent.com" for request in requests) == 2
