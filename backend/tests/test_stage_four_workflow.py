"""Deterministic API integration, not real GitHub or model-quality acceptance."""
from sqlalchemy import func, select

from app.models.domain import SourceChunk, SourceDocument
from app.models.graph import KnowledgeEntity, KnowledgeRelationship
from tests.test_code_search import search
from tests.test_graph import confirm
from tests.test_java_structure import upload_java
from tests.test_repositories import resolve_repository
from tests.test_sources import create_project


def test_forty_file_repository_search_navigation_and_repeat_import(client, db_session):
    project = create_project(client)
    repository = resolve_repository(client, project, "stage-four-fixture")
    sources = []
    for number in range(40):
        sources.append(upload_java(client, project, repository_id=repository["id"], name=f"Service{number}.java",
                                   relative_path=f"src/example/Service{number}.java",
                                   content=f"package example;\npublic class Service{number} {{\n    void execute{number}() {{}}\n}}\n"))
    result = search(client, project, "execute", kind="method", repository_id=repository["id"])
    assert result["scanned_source_count"] == result["matched_count"] == 40 and not result["truncated"]
    assert {hit["name"] for hit in result["items"]} == {f"execute{number}" for number in range(40)}
    hit = next(hit for hit in result["items"] if hit["name"] == "execute37")
    assert hit["source_id"] == sources[37]["source_id"]
    exact = client.get(f"/api/v1/projects/{project}/sources/{hit['source_id']}/chunks/{hit['chunk_id']}")
    assert exact.status_code == 200
    assert exact.json()["position"] == hit["chunk_position"]
    assert exact.json()["start_line"] <= hit["start_line"] <= exact.json()["end_line"]
    assert "void execute37()" in exact.json()["content"]
    by_file = search(client, project, "src/example/Service37.java", repository_id=repository["id"])
    assert {item["source_id"] for item in by_file["items"]} == {sources[37]["source_id"]}
    counts = [db_session.scalar(select(func.count()).select_from(model)) for model in (SourceDocument, SourceChunk)]
    for number in range(40):
        duplicate = upload_java(client, project, repository_id=repository["id"], name=f"Service{number}.java",
                                relative_path=f"src/example/Service{number}.java",
                                content=f"package example;\npublic class Service{number} {{\n    void execute{number}() {{}}\n}}\n")
        assert duplicate["source_id"] == sources[number]["source_id"] and duplicate["task_id"] == sources[number]["task_id"]
    assert [db_session.scalar(select(func.count()).select_from(model)) for model in (SourceDocument, SourceChunk)] == counts
    assert db_session.scalar(select(func.count()).select_from(KnowledgeEntity)) == 0
    assert db_session.scalar(select(func.count()).select_from(KnowledgeRelationship)) == 0
