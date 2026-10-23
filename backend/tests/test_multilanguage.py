import hashlib
import uuid

import httpx
import pytest
from sqlalchemy import func, select

from app import worker
from app.api.dependencies import get_current_user_id
from app.core.config import Settings
from app.core.identity import DEVELOPMENT_USER_ID
from app.main import app
from app.models.graph import KnowledgeEntity
from app.services import code_source
from app.services.source_languages import SOURCE_TYPE_BY_SUFFIX
from tests.test_github_import import create_project, install_github_mock, register_github


SAMPLES = [
    ("python", "py", '@decorator\nclass Orders:\n    label: str = "中文"\n    async def save(self):\n        return "def fake(): pass"\n', {"Orders", "Orders.label", "Orders.save"}),
    ("javascript", "js", 'class Orders {\n  label = "function fake() {}";\n  save() { return 1; }\n}\nexport const load = () => 1;\n', {"Orders", "Orders.label", "Orders.save", "load"}),
    ("jsx", "jsx", 'export const View = () => <section>中文</section>;\n', {"View"}),
    ("typescript", "ts", 'interface Order {\n  id: string;\n  save(): void;\n}\nexport function load(): string { return ""; }\n', {"Order", "Order.id", "Order.save", "load"}),
    ("tsx", "tsx", 'export const View = (props: {name: string}) => <div>{props.name}</div>;\n', {"View"}),
    ("go", "go", 'package demo\ntype Orders struct {\n Label string\n}\nfunc (o *Orders) Save() int { return 1 }\nfunc Load() {}\n', {"Orders", "Orders.Label", "Orders.Save", "Load"}),
    ("c", "c", 'struct Orders {\n int label;\n};\nint save(int n) { return n; }\nint load(void);\n', {"Orders", "Orders.label", "save", "load"}),
    ("cpp", "cpp", 'namespace demo {\nclass Orders {\n int label;\n void save() {}\n};\n}\n', {"demo.Orders", "demo.Orders.label", "demo.Orders.save"}),
    ("csharp", "cs", 'namespace Demo {\npublic class Orders {\n string label;\n public int Count { get; set; }\n public void Save() {}\n}\n}\n', {"Demo.Orders", "Demo.Orders.label", "Demo.Orders.Count", "Demo.Orders.Save"}),
]


@pytest.mark.parametrize("language,extension,content,names", SAMPLES)
def test_outline_and_chunks_are_lossless_stable_and_syntax_aware(language, extension, content, names):
    source = uuid.uuid4()
    content = content.replace("\n", "\r\n")
    parsed = code_source.analyze_code(content, source_id=source, language=language)
    assert not parsed.has_syntax_errors
    assert not parsed.truncated
    assert {item.qualified_name for item in parsed.symbols} == names
    assert "".join(item.content for item in parsed.chunks) == content
    lines = content.splitlines(keepends=True)
    for index, chunk in enumerate(parsed.chunks):
        assert chunk.position == index
        assert chunk.content == "".join(lines[chunk.start_line - 1:chunk.end_line])
        assert chunk.content_sha256 == hashlib.sha256(chunk.content.encode()).hexdigest()
        assert chunk.end_line - chunk.start_line < code_source.MAX_CHUNK_LINES
    assert parsed == code_source.analyze_code(content, source_id=source, language=language)
    other = code_source.analyze_code(content, source_id=uuid.uuid4(), language=language)
    assert not ({item.id for item in parsed.symbols} & {item.id for item in other.symbols})


@pytest.mark.parametrize("language,extension,content,names", SAMPLES)
def test_upload_worker_outline_search_and_exact_source_navigation(client, db_session, language, extension, content, names):
    project = create_project(client)
    url = f"/api/v1/projects/{project}/sources"
    data = {"relative_path": f"src/Orders.{extension}"}
    files = {"file": (f"Orders.{extension}", content.encode())}
    uploaded = client.post(url, data=data, files=files)
    assert uploaded.status_code == 202, uploaded.text
    upload = uploaded.json()
    assert client.post(url, data=data, files=files).json() == upload
    detail_url = f"/api/v1/sources/{upload['source_id']}"
    assert client.get(detail_url).json()["source_type"] == language
    assert client.get(detail_url + "/code-structure").status_code == 409
    task = worker.process_next(db_session, user_id=DEVELOPMENT_USER_ID, settings=Settings(_env_file=None))
    assert str(task.id) == upload["task_id"]
    assert task.status.value == "succeeded"
    outline = client.get(detail_url + "/code-structure").json()
    assert outline["language"] == language
    assert {item["qualified_name"] for item in outline["symbols"]} == names
    assert not outline["calls"] and not outline["cross_file_calls"]
    result = client.get(f"/api/v1/projects/{project}/code-symbols", params={"q": "src/Orders"}).json()
    assert not result["has_syntax_errors"]
    assert len(result["items"]) == len(names)
    for hit in result["items"]:
        assert hit["language"] == language
        assert hit["id"] in {symbol["id"] for symbol in outline["symbols"]}
        chunk = client.get(f"/api/v1/projects/{project}/sources/{hit['source_id']}/chunks/{hit['chunk_id']}").json()
        assert chunk["start_line"] <= hit["start_line"] <= chunk["end_line"]
    assert client.post(f"/api/v1/tasks/{upload['task_id']}/run").json()["status"] == "succeeded"
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEntity)) == 0


@pytest.mark.parametrize("suffix,language", [(ext, lang) for ext, lang in SOURCE_TYPE_BY_SUFFIX.items() if lang not in {"java", "markdown"}])
def test_every_extension_is_inferred_case_insensitively(client, suffix, language):
    project = create_project(client)
    response = client.post(f"/api/v1/projects/{project}/sources", files={"file": ("source" + suffix.upper(), b"// source\n")})
    assert response.status_code == 202, response.text
    assert client.get(f"/api/v1/sources/{response.json()['source_id']}").json()["source_type"] == language


def test_unicode_line_separators_decorators_comments_and_long_chunks():
    content = '# 中文\r\ntext = "hello\u2028world"\r\n@decorator\r\ndef save():\r\n    return 1\r\n' + "# tail\r\n" * 250
    parsed = code_source.analyze_code(content, source_id=uuid.uuid4(), language="python")
    symbol = next(item for item in parsed.symbols if item.name == "save")
    assert (symbol.start_line, symbol.end_line) == (4, 6)
    assert "".join(item.content for item in parsed.chunks) == content
    assert max(item.end_line - item.start_line for item in parsed.chunks) < code_source.MAX_CHUNK_LINES


def test_syntax_error_is_explicit_without_losing_original(client):
    project = create_project(client)
    content = "def broken(:\n    pass\n"
    upload = client.post(f"/api/v1/projects/{project}/sources", files={"file": ("broken.py", content.encode())}).json()
    assert client.post(f"/api/v1/tasks/{upload['task_id']}/run").json()["status"] == "succeeded"
    root = f"/api/v1/sources/{upload['source_id']}"
    outline = client.get(root + "/code-structure").json()
    assert outline["has_syntax_errors"]
    assert not outline["symbols"]
    assert "".join(item["content"] for item in client.get(root + "/chunks").json()["items"]) == content
    assert client.get(f"/api/v1/projects/{project}/code-symbols", params={"q": "broken"}).json()["has_syntax_errors"]


def test_limits_preserve_text_and_mark_incomplete(monkeypatch):
    content = "\n".join(f"def f{i}(): pass" for i in range(12))
    monkeypatch.setattr(code_source, "MAX_SYMBOLS", 3)
    parsed = code_source.analyze_code(content, source_id=uuid.uuid4(), language="python")
    assert parsed.truncated and len(parsed.symbols) == 3
    assert "".join(item.content for item in parsed.chunks) == content
    monkeypatch.setattr(code_source, "MAX_VISITS", 2)
    assert code_source.analyze_code(content, source_id=uuid.uuid4(), language="python").truncated


@pytest.mark.parametrize("language", ["c", "cpp"])
def test_function_pointers_are_not_reported_as_callable_definitions(language):
    content = "struct Hooks { int (*callback)(int); };\nint (*global_callback)(int);\nint *allocate(void);\nint (*factory(void))(int);\n"
    parsed = code_source.analyze_code(content, source_id=uuid.uuid4(), language=language)
    assert not parsed.has_syntax_errors
    methods = {item.name for item in parsed.symbols if item.kind == "method"}
    assert methods == {"allocate", "factory"}
    assert any(item.name == "callback" and item.kind == "field" for item in parsed.symbols)


def test_type_repository_project_and_user_boundaries(client, db_session):
    project = create_project(client)
    repository = client.post(f"/api/v1/projects/{project}/repositories/resolve", json={"name": "mixed"}).json()["id"]
    url = f"/api/v1/projects/{project}/sources"
    raw = b"// identical bytes\n"
    uploads = []
    for filename in ("same.js", "same.ts"):
        response = client.post(url, data={"repository_id": repository, "relative_path": filename}, files={"file": (filename, raw)})
        assert response.status_code == 202
        uploads.append(response.json())
    assert uploads[0]["source_id"] != uploads[1]["source_id"]
    assert client.post(url, data={"source_type": "java"}, files={"file": ("bad.py", raw)}).status_code == 422
    assert client.post(url, files={"file": ("bad.py", b"\xff")}).status_code == 422
    assert client.post(url, files={"file": ("empty.py", b" \n")}).status_code == 422
    other = create_project(client)
    assert client.get(f"/api/v1/projects/{other}/code-symbols", params={"q": "same", "repository_id": repository}).status_code == 404
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(f"/api/v1/sources/{uploads[0]['source_id']}/code-structure").status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)


def test_github_mixed_language_sync_and_pinned_cache(client, monkeypatch):
    requests = []
    bodies = {f"src/example.{ext}": content.encode() for _, ext, content, _ in SAMPLES}

    def respond(request):
        requests.append(request.url.path)
        path = request.url.path
        if path == "/repos/example/demo":
            return httpx.Response(200, json={"default_branch": "main"})
        if path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "a" * 40, "commit": {"tree": {"sha": "b" * 40}}})
        if "/git/trees/" in path:
            return httpx.Response(200, json={"truncated": False, "tree": [
                {"path": filename, "sha": filename.split(".")[-1], "type": "blob", "size": len(body)}
                for filename, body in bodies.items()
            ]})
        return httpx.Response(200, content=bodies[f"src/example.{path.rsplit('/', 1)[-1]}"])

    install_github_mock(monkeypatch, respond)
    project = create_project(client)
    repo = register_github(client, project)
    url = f"/api/v1/projects/{project}/repositories/{repo['id']}/sync-github"
    first = client.post(url, json={})
    assert first.status_code == 200, first.text
    assert first.json()["imported_count"] == len(SAMPLES)
    before = len(requests)
    second = client.post(url, json={})
    assert second.json()["snapshot_id"] == first.json()["snapshot_id"]
    assert all("/git/" not in path for path in requests[before:])
    before = len(requests)
    rescanned = client.post(url, json={"rescan": True})
    assert rescanned.status_code == 200, rescanned.text
    assert rescanned.json()["snapshot_id"] != first.json()["snapshot_id"]
    assert any("/git/trees/" in path for path in requests[before:])
    assert not any("/git/blobs/" in path for path in requests[before:])
    assert rescanned.json()["unchanged_count"] == len(SAMPLES)
    for item in first.json()["items"]:
        assert client.post(f"/api/v1/tasks/{item['task_id']}/run").json()["status"] == "succeeded"
    search = client.get(f"/api/v1/projects/{project}/code-symbols", params={"q": "example", "top_k": 50}).json()
    assert {item["language"] for item in search["items"]} == {item[0] for item in SAMPLES}
    assert all("/blob/" + "a" * 40 in item["git_url"] and "#L" in item["git_url"] for item in search["items"])


def test_existing_complete_snapshot_can_discover_new_languages_on_rescan(client, monkeypatch):
    from app.services import ingestion
    files = {"README.md": b"# Demo\n", "main.py": b"def save(): pass\n"}

    def respond(request):
        path = request.url.path
        if path == "/repos/example/demo":
            return httpx.Response(200, json={"default_branch": "main"})
        if path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "a" * 40, "commit": {"tree": {"sha": "b" * 40}}})
        if "/git/trees/" in path:
            return httpx.Response(200, json={"truncated": False, "tree": [
                {"path": filename, "sha": filename, "type": "blob", "size": len(body)} for filename, body in files.items()
            ]})
        return httpx.Response(200, content=files[path.rsplit("/", 1)[-1]])

    install_github_mock(monkeypatch, respond)
    project = create_project(client)
    repo = register_github(client, project)
    url = f"/api/v1/projects/{project}/repositories/{repo['id']}/sync-github"
    with monkeypatch.context() as old:
        old.setattr(ingestion, "SOURCE_TYPE_BY_SUFFIX", {".md": "markdown", ".java": "java"})
        previous = client.post(url, json={}).json()
    assert previous["imported_count"] == 1 and not previous["truncated"]
    assert client.post(url, json={}).json()["snapshot_id"] == previous["snapshot_id"]
    refreshed = client.post(url, json={"rescan": True}).json()
    assert refreshed["imported_count"] == refreshed["unchanged_count"] == 1
    assert client.get(f"/api/v1/projects/{project}/sources").json()["total"] == 2
