import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_id
from app.main import app
from app.models.domain import Project, SourceDocument, utc_now
from app.services import code_search, java_source
from tests.test_java_structure import upload_java
from tests.test_sources import create_project


def search(client: TestClient, project: str, query: str, **params) -> dict:
    response = client.get(f"/api/v1/projects/{project}/code-symbols", params={"q": query, **params})
    assert response.status_code == 200, response.text
    return response.json()


def upload(client: TestClient, project: str, name="Orders", *, repository=None, parse=True, body="") -> dict:
    return upload_java(
        client, project, name=f"{name}.java", relative_path=f"src/{name}.java",
        repository_id=repository, parse=parse,
        content=body or f"package example;\npublic class {name} {{\n    String label;\n    void save() {{}}\n}}\n",
    )


def test_search_shares_outline_ids_lines_and_exact_chunk_location(client: TestClient) -> None:
    project = create_project(client)
    source = upload(client, project)
    result = search(client, project, "  SAVE  ")
    assert result["query"] == "SAVE"
    assert result["scanned_source_count"] == result["matched_count"] == 1
    assert not result["truncated"]
    hit = result["items"][0]
    assert hit["qualified_name"] == "Orders.save"
    assert hit["source_id"] == source["source_id"]
    assert hit["task_id"] == source["task_id"]
    assert hit["git_url"] is None
    outline = client.get(f"/api/v1/sources/{source['source_id']}/code-structure").json()
    method = next(item for item in outline["symbols"] if item["kind"] == "method")
    assert all(hit[key] == method[key] for key in method)
    chunks = client.get(f"/api/v1/sources/{source['source_id']}/chunks").json()["items"]
    chunk = next(item for item in chunks if item["id"] == hit["chunk_id"])
    assert chunk["position"] == hit["chunk_position"]
    assert chunk["start_line"] <= hit["start_line"] <= chunk["end_line"]


@pytest.mark.parametrize("query, kind, names", [
    ("orders", None, ["Orders", "label", "save"]),
    ("SRC/ORDERS.JAVA", "method", ["save"]),
    ("Orders", "type", ["Orders"]),
    ("label", "field", ["label"]),
    ("not-found", None, []),
    ("%", None, []),
])
def test_case_insensitive_literal_name_path_and_kind_filters(client, query, kind, names) -> None:
    project = create_project(client)
    upload(client, project)
    result = search(client, project, query, **({"kind": kind} if kind else {}))
    assert sorted(item["name"] for item in result["items"]) == sorted(names)


def test_repository_project_user_readiness_and_language_boundaries(client: TestClient) -> None:
    project = create_project(client)
    repositories = [client.post(f"/api/v1/projects/{project}/repositories/resolve", json={"name": name}).json()["id"]
                    for name in ("first", "second")]
    first = upload(client, project, repository=repositories[0])
    upload(client, project, repository=repositories[1])
    upload(client, project, "Unassigned")
    upload(client, project, "Pending", parse=False)
    client.post(f"/api/v1/projects/{project}/sources", files={"file": ("Orders.md", b"# Orders")})
    other_project = create_project(client)
    upload(client, other_project, "OtherProject")
    result = search(client, project, "save")
    assert len(result["items"]) == 3
    assert result["scanned_source_count"] == 3
    filtered = search(client, project, "save", repository_id=repositories[0])
    assert len(filtered["items"]) == 1
    assert filtered["items"][0]["source_id"] == first["source_id"]
    assert filtered["items"][0]["repository_name"] == "first"
    assert client.get(f"/api/v1/projects/{other_project}/code-symbols", params={"q": "save", "repository_id": repositories[0]}).status_code == 404
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    try:
        assert client.get(f"/api/v1/projects/{project}/code-symbols", params={"q": "save"}).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user_id)


def test_archived_project_cannot_be_searched(client: TestClient, db_session: Session) -> None:
    project = create_project(client)
    upload(client, project)
    db_session.get(Project, uuid.UUID(project)).archived_at = utc_now()
    db_session.commit()
    assert client.get(f"/api/v1/projects/{project}/code-symbols", params={"q": "save"}).status_code == 404


def test_versions_remain_distinct_and_result_limit_reports_truncation(client: TestClient) -> None:
    project = create_project(client)
    first = upload(client, project)
    second = upload(client, project, body="class Orders {\n    void save() { updated(); }\n}\n")
    result = search(client, project, "save", limit=1)
    assert result["matched_count"] == 2
    assert len(result["items"]) == 1
    assert result["truncated"]
    all_hits = search(client, project, "save")
    assert {item["source_id"] for item in all_hits["items"]} == {first["source_id"], second["source_id"]}
    assert all_hits == search(client, project, "save")


def test_source_byte_and_symbol_limits_are_explicit(client: TestClient, monkeypatch) -> None:
    project = create_project(client)
    upload(client, project, "First")
    upload(client, project, "Second")
    monkeypatch.setattr(code_search, "MAX_SEARCH_SOURCES", 1)
    result = search(client, project, "Second")
    assert result["items"] == []
    assert result["scanned_source_count"] == 1
    assert result["truncated"]
    monkeypatch.setattr(code_search, "MAX_SEARCH_SOURCES", 100)
    monkeypatch.setattr(code_search, "MAX_SEARCH_BYTES", 1)
    result = search(client, project, "save")
    assert result["items"] == [] and result["truncated"]
    assert result["scanned_source_count"] == 0
    monkeypatch.setattr(code_search, "MAX_SEARCH_BYTES", 20 * 1024 * 1024)
    monkeypatch.setattr(java_source, "MAX_STRUCTURE_SYMBOLS", 1)
    result = search(client, project, "save")
    assert result["items"] == [] and result["truncated"]


def test_search_can_target_a_later_chunk_page(client: TestClient) -> None:
    project = create_project(client)
    body = "class Large {\n" + "".join(f"    void method{i}() {{}}\n" for i in range(35)) + "}\n"
    source = upload(client, project, "Large", body=body)
    hit = search(client, project, "method34")["items"][0]
    assert hit["chunk_position"] >= 20
    chunks = client.get(f"/api/v1/sources/{source['source_id']}/chunks",
                        params={"page": hit["chunk_position"] // 20 + 1}).json()
    assert hit["chunk_id"] in {chunk["id"] for chunk in chunks["items"]}


def test_missing_parse_task_does_not_hide_ready_symbols(client: TestClient, db_session: Session) -> None:
    project = create_project(client)
    source = upload(client, project)
    # Legacy source metadata can remain ready without a current task mapping.
    document = db_session.get(SourceDocument, uuid.UUID(source["source_id"]))
    document.tasks.clear()
    db_session.commit()
    hit = search(client, project, "save")["items"][0]
    assert hit["task_id"] is None
    assert hit["chunk_id"] is not None


def test_github_symbol_link_is_commit_and_line_pinned(client: TestClient, monkeypatch) -> None:
    from tests.test_github_import import install_github_mock, register_github
    from tests.test_github_sync_recovery import Remote

    remote = Remote(blobs={"java": b"class Remote {\n    void save() {}\n}\n"})
    remote.files(("src/Remote.java", "java"))
    install_github_mock(monkeypatch, remote.respond)
    project = create_project(client)
    repository = register_github(client, project)["id"]
    imported = client.post(f"/api/v1/projects/{project}/repositories/{repository}/sync-github", json={}).json()
    client.post(f"/api/v1/tasks/{imported['items'][0]['task_id']}/run")
    hit = search(client, project, "save")["items"][0]
    assert hit["git_url"] == f"https://github.com/example/demo/blob/{'a' * 40}/src/Remote.java#L2"


@pytest.mark.parametrize("params", [
    {}, {"q": ""}, {"q": "   "}, {"q": "x" * 201}, {"q": "x", "limit": 0},
    {"q": "x", "limit": 101}, {"q": "x", "kind": "unknown"}, {"q": "x", "repository_id": "bad"},
])
def test_invalid_queries_are_rejected(client: TestClient, params: dict) -> None:
    project = create_project(client)
    assert client.get(f"/api/v1/projects/{project}/code-symbols", params=params).status_code == 422
