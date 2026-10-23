"""Opt-in real public GitHub reads; no token, private data or model invocation."""
import json
import os
from pathlib import Path
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes import repositories as routes
from app.core.config import Settings
from app.models.domain import SourceChunk, SourceDocument
from app.models.graph import KnowledgeEntity
from app.services import deepseek, embeddings
from tests.test_native_acceptance import independent_client
from tests.test_sources import create_project

pytestmark = pytest.mark.skipif(not (os.environ.get("KA_ACCEPTANCE_SCHEMA") and os.environ.get("KA_GITHUB_ACCEPTANCE") == "1"),
                                reason="requires explicit public GitHub acceptance in a disposable PostgreSQL schema")


def test_real_public_repository_import_search_commit_and_repeat(monkeypatch):
    settings = Settings(_env_file=None, github_token=None, deepseek_api_key=None, embedding_api_key=None,
                        github_api_base_url="https://api.github.com", github_timeout_seconds=30,
                        github_import_max_files=30)
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    def no_models(*args, **kwargs):
        pytest.fail("Model invocation is explicitly excluded from public GitHub acceptance")
    monkeypatch.setattr(deepseek, "extract_candidates", no_models)
    monkeypatch.setattr(deepseek, "answer_question", no_models)
    monkeypatch.setattr(embeddings, "embed_texts", no_models)
    with independent_client() as (client, engine):
        project = create_project(client)
        response = client.post(f"/api/v1/projects/{project}/repositories/resolve-github",
                               json={"remote_url": "https://github.com/spring-projects/spring-petclinic"})
        assert response.status_code == 200, response.text
        repository = response.json()["id"]
        url = f"/api/v1/projects/{project}/repositories/{repository}"
        response = client.post(url + "/sync-github", json={})
        assert response.status_code == 200, response.text
        first = response.json()
        imported = [item for item in first["items"] if item["source_id"]]
        assert 10 <= len(imported) <= 50, first
        for item in imported:
            result = client.post(f"/api/v1/tasks/{item['task_id']}/run")
            assert result.status_code == 200 and result.json()["status"] == "succeeded"
        files = client.get(url + f"/snapshots/{first['snapshot_id']}/files", params={"page_size": 100}).json()
        assert len(files["items"]) >= len(imported)
        with Session(engine) as db:
            sources = list(db.scalars(select(SourceDocument).where(SourceDocument.project_id == uuid.UUID(project))))
            assert {item.source_type for item in sources} >= {"markdown", "java"}
            java = next(item for item in sources if item.source_type == "java")
            source_id = str(java.id)
            filename = java.relative_path
            before_sources = len(sources)
            before_chunks = db.scalar(select(func.count()).select_from(SourceChunk).where(SourceChunk.project_id == uuid.UUID(project)))
        structure = client.get(f"/api/v1/sources/{source_id}/code-structure").json()
        symbol = next(item for item in structure["symbols"] if item["kind"] == "type")
        search = client.get(f"/api/v1/projects/{project}/code-symbols", params={"q": filename, "repository_id": repository}).json()
        hit = next(item for item in search["items"] if item["id"] == symbol["id"])
        assert first["commit_sha"] in hit["git_url"] and "#L" in hit["git_url"]
        chunk = client.get(f"/api/v1/projects/{project}/sources/{source_id}/chunks/{hit['chunk_id']}").json()
        assert chunk["start_line"] <= symbol["start_line"] <= chunk["end_line"]
        # First pin may create a separate ref snapshot, but must reuse every source/chunk.
        pinned = client.post(url + "/sync-github", json={"ref": first["commit_sha"]})
        assert pinned.status_code == 200, pinned.text
        repeated = client.post(url + "/sync-github", json={"ref": first["commit_sha"]})
        assert repeated.status_code == 200, repeated.text
        assert {item["source_id"] for item in repeated.json()["items"] if item["source_id"]} == {item["source_id"] for item in imported}
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(SourceDocument).where(SourceDocument.project_id == uuid.UUID(project))) == before_sources
            assert db.scalar(select(func.count()).select_from(SourceChunk).where(SourceChunk.project_id == uuid.UUID(project))) == before_chunks
            assert db.scalar(select(func.count()).select_from(KnowledgeEntity).where(KnowledgeEntity.project_id == uuid.UUID(project))) == 0
        commit_url = url + f"/snapshots/{first['snapshot_id']}/commit-source"
        commit = client.post(commit_url).json()
        assert commit["git_url"].endswith("/commit/" + first["commit_sha"])
        assert client.post(f"/api/v1/tasks/{commit['task_id']}/run").json()["status"] == "succeeded"
        assert client.post(commit_url).json()["source_id"] == commit["source_id"]
        report = {"repository": "https://github.com/spring-projects/spring-petclinic", "commit_sha": first["commit_sha"],
                  "imported_source_count": len(imported), "initial_chunk_count": before_chunks, "truncated": first["truncated"],
                  "symbol": symbol["qualified_name"], "file": filename, "git_url": hit["git_url"],
                  "repeat_sources_and_chunks_unchanged": True, "commit_message_import_reused": True,
                  "real_github": True, "real_models_called": False, "formal_knowledge_automatically_created": False}
        report["configured_file_budget"] = settings.github_import_max_files
        if os.environ.get("KA_GITHUB_REPORT"):
            with Path(os.environ["KA_GITHUB_REPORT"]).open("x", encoding="utf-8") as output:
                json.dump(report, output, indent=2, ensure_ascii=False)
