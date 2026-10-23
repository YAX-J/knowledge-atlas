"""Incremental snapshots recover bounded work without mixing parser identities."""

import uuid
from dataclasses import dataclass, field

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes import repositories as repository_routes
from app.core.config import Settings
from app.models.domain import RepositorySnapshotFile
from app.services import github_import
from tests.test_github_import import create_project, install_github_mock, register_github


@dataclass
class Remote:
    blobs: dict[str, bytes] = field(default_factory=lambda: {"a": b"# A\n", "b": b"# B\n"})
    entries: list[dict] = field(default_factory=list)
    commit: str = "a"
    truncated: bool = False
    requests: list[str] = field(default_factory=list)

    def files(self, *items: tuple[str, str]) -> None:
        self.entries = [
            {"path": path, "type": "blob", "sha": blob, "size": len(self.blobs[blob])}
            for path, blob in items
        ]

    def respond(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.requests.append(path)
        if path == "/repos/example/demo":
            return httpx.Response(200, json={"id": 42, "default_branch": "main"})
        if "/commits/" in path:
            return httpx.Response(200, json={
                "sha": self.commit * 40,
                "commit": {"tree": {"sha": "t" * 40}, "message": "Public fixture"},
            })
        if "/git/trees/" in path:
            return httpx.Response(200, json={"tree": self.entries, "truncated": self.truncated})
        if "/git/blobs/" in path:
            return httpx.Response(200, content=self.blobs[path.rsplit("/", 1)[-1]])
        raise AssertionError(path)

    @property
    def blob_requests(self) -> list[str]:
        return [path.rsplit("/", 1)[-1] for path in self.requests if "/git/blobs/" in path]


@pytest.fixture
def remote(monkeypatch) -> Remote:
    result = Remote()
    install_github_mock(monkeypatch, result.respond)
    return result


def endpoint(client: TestClient) -> tuple[str, str, str]:
    project = create_project(client)
    repository = register_github(client, project)["id"]
    return project, repository, f"/api/v1/projects/{project}/repositories/{repository}/sync-github"


def sync(client: TestClient, url: str) -> dict:
    response = client.post(url, json={})
    assert response.status_code == 200, response.text
    return response.json()


def test_configured_file_budget_can_expand_without_losing_existing_sources(client, monkeypatch, remote):
    remote.files(("A.md", "a"), ("B.md", "b"))
    settings = repository_routes.get_settings().model_copy(update={"github_import_max_files": 1})
    monkeypatch.setattr(repository_routes, "get_settings", lambda: settings)
    _, _, url = endpoint(client)
    first = sync(client, url)
    assert first["truncated"] and not first["deletion_detection_complete"]
    assert [item["path"] for item in first["items"]] == ["A.md"]
    assert remote.blob_requests == ["a"]
    settings = settings.model_copy(update={"github_import_max_files": 2})
    second = sync(client, url)
    assert not second["truncated"] and second["deletion_detection_complete"]
    assert [item["path"] for item in second["items"]] == ["A.md", "B.md"]
    assert second["items"][0]["source_id"] == first["items"][0]["source_id"]
    assert remote.blob_requests == ["a", "b"]


@pytest.mark.parametrize("budget", [0, 51])
def test_github_file_budget_rejects_values_outside_hard_cap(budget):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(_env_file=None, github_import_max_files=budget)


def test_same_commit_recovers_byte_budget_then_returns_complete_snapshot(
    client: TestClient, monkeypatch, remote: Remote,
) -> None:
    monkeypatch.setattr(github_import, "MAX_GITHUB_IMPORT_BYTES", 4)
    remote.files(("A.md", "a"), ("B.md", "b"))
    project, repository, url = endpoint(client)
    first = sync(client, url)
    assert first["truncated"]
    assert first["skipped_count"] == 1
    assert first["items"][1]["error_code"] == "GITHUB_IMPORT_TOTAL_SIZE_EXCEEDED"
    second = sync(client, url)
    assert second["snapshot_id"] != first["snapshot_id"]
    assert second["commit_sha"] == first["commit_sha"]
    assert (second["imported_count"], second["unchanged_count"], second["skipped_count"]) == (1, 1, 0)
    assert not second["truncated"]
    assert second["deletion_detection_complete"]
    assert second["items"][0]["source_id"] == first["items"][0]["source_id"]
    remote.requests.clear()
    third = sync(client, url)
    assert third["snapshot_id"] == second["snapshot_id"]
    assert third["unchanged_count"] == 2
    assert len(remote.requests) == 2  # Repository and ref only, no tree/blob.
    snapshots = client.get(f"/api/v1/projects/{project}/repositories/{repository}/snapshots").json()
    assert snapshots["total"] == 2
    assert snapshots["items"][0]["downloaded_bytes"] == 4
    assert snapshots["items"][1]["skipped_count"] == 1


@pytest.mark.parametrize("limit_kind", ["tree", "file_count"])
def test_same_commit_recovers_tree_or_file_selection_truncation(
    client: TestClient, monkeypatch, remote: Remote, limit_kind: str,
) -> None:
    remote.files(("A.md", "a"), ("B.md", "b"))
    if limit_kind == "tree":
        remote.truncated = True
        remote.files(("A.md", "a"))
    else:
        monkeypatch.setattr(github_import, "MAX_GITHUB_IMPORT_FILES", 1)
    _, _, url = endpoint(client)
    first = sync(client, url)
    assert first["truncated"]
    remote.truncated = False
    remote.files(("A.md", "a"), ("B.md", "b"))
    monkeypatch.setattr(github_import, "MAX_GITHUB_IMPORT_FILES", 50)
    second = sync(client, url)
    assert second["snapshot_id"] != first["snapshot_id"]
    assert not second["truncated"]
    assert second["unchanged_count"] == second["imported_count"] == 1
    assert remote.blob_requests == ["a", "b"]


@pytest.mark.parametrize("declared_size", [1, 5])
def test_same_commit_retries_size_skips_after_limit_increase(
    client: TestClient, monkeypatch, remote: Remote, declared_size: int,
) -> None:
    remote.blobs["a"] = b"12345"
    remote.files(("A.md", "a"))
    remote.entries[0]["size"] = declared_size
    monkeypatch.setattr(repository_routes, "get_settings", lambda: Settings(
        _env_file=None, github_api_base_url="https://api.github.test", max_upload_bytes=4,
    ))
    _, _, url = endpoint(client)
    first = sync(client, url)
    assert first["items"][0]["error_code"] == "SOURCE_TOO_LARGE"
    assert not first["truncated"]
    monkeypatch.setattr(repository_routes, "get_settings", lambda: Settings(
        _env_file=None, github_api_base_url="https://api.github.test", max_upload_bytes=10,
    ))
    second = sync(client, url)
    assert second["snapshot_id"] != first["snapshot_id"]
    assert second["imported_count"] == 1
    assert second["skipped_count"] == 0


@pytest.mark.parametrize("path, raw, code", [
    ("A.md", b"", "SOURCE_EMPTY"),
    ("A.md", b"\xff", "SOURCE_ENCODING_INVALID"),
    ("../A.md", b"# A", "SOURCE_PATH_INVALID"),
])
def test_deterministic_invalid_blobs_keep_same_commit_shortcut(
    client: TestClient, remote: Remote, path: str, raw: bytes, code: str,
) -> None:
    remote.blobs["a"] = raw
    remote.files((path, "a"))
    _, _, url = endpoint(client)
    first = sync(client, url)
    assert first["items"][0]["error_code"] == code
    remote.requests.clear()
    second = sync(client, url)
    assert second["snapshot_id"] == first["snapshot_id"]
    assert second["skipped_count"] == 1
    assert len(remote.requests) == 2


def test_cross_type_rename_creates_correct_parser_and_can_reuse_older_typed_blob(
    client: TestClient, remote: Remote,
) -> None:
    remote.blobs["a"] = b"class App {}\n"
    remote.files(("App.md", "a"))
    _, _, url = endpoint(client)
    markdown = sync(client, url)["items"][0]
    remote.commit = "b"
    remote.files(("App.JAVA", "a"))
    second = sync(client, url)
    java = next(item for item in second["items"] if item["path"] == "App.JAVA")
    assert (second["imported_count"], second["renamed_count"], second["deleted_count"]) == (1, 0, 1)
    assert java["source_id"] != markdown["source_id"]
    assert client.get(f"/api/v1/tasks/{java['task_id']}").json()["type"] == "code_parsing"
    assert client.post(f"/api/v1/tasks/{java['task_id']}/run").json()["status"] == "succeeded"
    structure = client.get(f"/api/v1/sources/{java['source_id']}/code-structure").json()
    assert structure["symbols"][0]["name"] == "App"
    remote.commit = "c"
    remote.files(("App.md", "a"))
    third = sync(client, url)
    restored = next(item for item in third["items"] if item["path"] == "App.md")
    assert third["reused_count"] == 1
    assert restored["source_id"] == markdown["source_id"]
    assert remote.blob_requests == ["a", "a"]
    assert client.get(f"/api/v1/sources/{markdown['source_id']}").json()["relative_path"] == "App.md"


def test_same_blob_copy_across_types_does_not_share_source_or_task(
    client: TestClient, remote: Remote,
) -> None:
    remote.files(("App.md", "a"))
    _, _, url = endpoint(client)
    markdown = sync(client, url)["items"][0]
    remote.commit = "b"
    remote.files(("App.md", "a"), ("App.java", "a"))
    second = sync(client, url)
    by_path = {item["path"]: item for item in second["items"]}
    assert by_path["App.md"]["source_id"] == markdown["source_id"]
    assert by_path["App.java"]["source_id"] != markdown["source_id"]
    assert by_path["App.java"]["task_id"] != markdown["task_id"]
    assert (second["unchanged_count"], second["imported_count"]) == (1, 1)


def test_markdown_suffix_alias_rename_keeps_typed_reuse(client: TestClient, remote: Remote) -> None:
    remote.files(("A.md", "a"))
    _, _, url = endpoint(client)
    first = sync(client, url)["items"][0]
    remote.commit = "b"
    remote.files(("A.markdown", "a"))
    second = sync(client, url)
    assert second["renamed_count"] == 1
    assert second["items"][0]["source_id"] == first["source_id"]
    assert remote.blob_requests == ["a"]


@pytest.mark.parametrize("missing", ["source_id", "task_id", "both"])
def test_same_commit_repairs_missing_snapshot_links(
    client: TestClient, db_session: Session, remote: Remote, missing: str,
) -> None:
    remote.files(("A.md", "a"))
    _, _, url = endpoint(client)
    first = sync(client, url)
    record = db_session.scalar(select(RepositorySnapshotFile).where(
        RepositorySnapshotFile.snapshot_id == uuid.UUID(first["snapshot_id"]),
    ))
    if missing in {"source_id", "both"}:
        record.source_id = None
    if missing in {"task_id", "both"}:
        record.task_id = None
    db_session.commit()
    second = sync(client, url)
    assert second["snapshot_id"] != first["snapshot_id"]
    assert second["reused_count"] == 1
    assert second["items"][0]["source_id"] == first["items"][0]["source_id"]
    assert second["items"][0]["task_id"] == first["items"][0]["task_id"]


@pytest.mark.parametrize("foreign", ["repository", "project", "type", "task"])
def test_same_commit_rejects_foreign_or_wrongly_typed_cached_links(
    client: TestClient, db_session: Session, remote: Remote, foreign: str,
) -> None:
    remote.files(("A.md", "a"))
    project, repository, url = endpoint(client)
    first = sync(client, url)
    target_project = create_project(client) if foreign == "project" else project
    target_repository = repository if foreign in {"type", "task"} else client.post(
        f"/api/v1/projects/{target_project}/repositories/resolve", json={"name": "other"},
    ).json()["id"]
    uploaded = client.post(
        f"/api/v1/projects/{target_project}/sources",
        data={"repository_id": target_repository, "relative_path": "Other.java" if foreign == "type" else "Other.md"},
        files={"file": ("Other.java" if foreign == "type" else "Other.md",
                         remote.blobs["a"] if foreign != "task" else b"# Different")},
    )
    assert uploaded.status_code == 202
    other = uploaded.json()
    record = db_session.scalar(select(RepositorySnapshotFile).where(
        RepositorySnapshotFile.snapshot_id == uuid.UUID(first["snapshot_id"]),
    ))
    if foreign != "task":
        record.source_id = uuid.UUID(other["source_id"])
    record.task_id = uuid.UUID(other["task_id"])
    db_session.commit()
    second = sync(client, url)
    assert second["snapshot_id"] != first["snapshot_id"]
    assert second["items"][0]["source_id"] == first["items"][0]["source_id"]
    assert second["items"][0]["task_id"] == first["items"][0]["task_id"]
    assert client.get(f"/api/v1/sources/{other['source_id']}").json()["relative_path"].startswith("Other.")


def test_truncated_tree_never_guesses_rename_or_changes_source_display_path(
    client: TestClient, remote: Remote,
) -> None:
    remote.files(("A.md", "a"))
    _, _, url = endpoint(client)
    first = sync(client, url)
    remote.commit = "b"
    remote.truncated = True
    remote.files(("B.md", "a"))
    second = sync(client, url)
    assert (second["renamed_count"], second["deleted_count"], second["reused_count"]) == (0, 0, 1)
    assert second["truncated"]
    assert client.get(f"/api/v1/sources/{first['items'][0]['source_id']}").json()["relative_path"] == "A.md"
    remote.truncated = False
    remote.files(("A.md", "a"), ("B.md", "a"))
    third = sync(client, url)
    assert not third["truncated"]
    assert third["renamed_count"] == third["deleted_count"] == 0
    assert remote.blob_requests == ["a"]
