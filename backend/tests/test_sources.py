import pytest
from fastapi.testclient import TestClient


def create_project(client: TestClient) -> str:
    response = client.post(
        "/api/v1/projects",
        json={"name": "知识导入测试", "description": ""},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_upload_markdown_creates_source_and_queued_task(client: TestClient) -> None:
    project_id = create_project(client)
    content = "# 事件一致性\n\n事务提交后发布领域事件。\n"

    upload_response = client.post(
        f"/api/v1/projects/{project_id}/sources",
        files={"file": ("decision.md", content.encode("utf-8"), "text/markdown")},
    )

    assert upload_response.status_code == 202
    upload = upload_response.json()
    assert upload["status"] == "queued"

    source_response = client.get(f"/api/v1/sources/{upload['source_id']}")
    assert source_response.status_code == 200
    source = source_response.json()
    assert source["original_name"] == "decision.md"
    assert source["repository_id"] is None
    assert source["repository_name"] is None
    assert source["git_url"] is None
    assert source["relative_path"] is None
    assert source["line_count"] == 3
    assert source["content_preview"] == content
    assert len(source["content_sha256"]) == 64

    task_response = client.get(f"/api/v1/tasks/{upload['task_id']}")
    assert task_response.status_code == 200
    task = task_response.json()
    assert task["source_id"] == upload["source_id"]
    assert task["status"] == "queued"
    assert task["stage"] == "uploaded"
    assert task["progress"] == 0


def test_rejects_unsupported_file_type(client: TestClient) -> None:
    project_id = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/sources",
        files={"file": ("secret.exe", b"not markdown", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_SOURCE_TYPE"


def test_rejects_empty_markdown(client: TestClient) -> None:
    project_id = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/sources",
        files={"file": ("empty.md", b"\n  \n", "text/markdown")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SOURCE_EMPTY"


def test_folder_relative_path_is_normalized_exposed_and_kept_on_reuse(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    content = b"package example;\nclass Decision {}\n"
    first = client.post(
        f"/api/v1/projects/{project_id}/sources",
        data={"source_type": "java", "relative_path": "sample\\src\\Decision.java"},
        files={"file": ("Decision.java", content, "text/x-java-source")},
    )
    assert first.status_code == 202

    source = client.get(f"/api/v1/sources/{first.json()['source_id']}").json()
    assert source["relative_path"] == "sample/src/Decision.java"
    listed = client.get(f"/api/v1/projects/{project_id}/sources").json()["items"]
    assert listed[0]["relative_path"] == "sample/src/Decision.java"

    reused = client.post(
        f"/api/v1/projects/{project_id}/sources",
        data={"source_type": "java", "relative_path": "sample/src/Decision.java"},
        files={"file": ("Decision.java", content, "text/x-java-source")},
    )
    assert reused.status_code == 202
    assert reused.json()["source_id"] == first.json()["source_id"]
    source = client.get(f"/api/v1/sources/{first.json()['source_id']}").json()
    assert source["relative_path"] == "sample/src/Decision.java"


def test_repository_scopes_paths_and_duplicate_reuse(client: TestClient) -> None:
    project_id = create_project(client)
    first_repository = client.post(
        f"/api/v1/projects/{project_id}/repositories/resolve",
        json={"name": "first"},
    ).json()
    second_repository = client.post(
        f"/api/v1/projects/{project_id}/repositories/resolve",
        json={"name": "second"},
    ).json()
    content = b"package example;\nclass Shared {}\n"

    def upload_to(repository_id: str, path: str):
        return client.post(
            f"/api/v1/projects/{project_id}/sources",
            data={
                "source_type": "java",
                "repository_id": repository_id,
                "relative_path": path,
            },
            files={"file": ("Shared.java", content, "text/x-java-source")},
        )

    first = upload_to(first_repository["id"], "src/Shared.java")
    reused = upload_to(first_repository["id"], "src/Shared.java")
    other_path = upload_to(first_repository["id"], "renamed/Shared.java")
    second = upload_to(second_repository["id"], "src/Shared.java")

    assert first.status_code == reused.status_code == second.status_code == 202
    assert reused.json()["source_id"] == first.json()["source_id"]
    assert reused.json()["task_id"] == first.json()["task_id"]
    assert other_path.status_code == 202
    assert other_path.json()["source_id"] != first.json()["source_id"]
    assert other_path.json()["task_id"] != first.json()["task_id"]
    other_detail = client.get(f"/api/v1/sources/{other_path.json()['source_id']}").json()
    assert other_detail["relative_path"] == "renamed/Shared.java"
    assert second.json()["source_id"] != first.json()["source_id"]
    detail = client.get(
        f"/api/v1/sources/{first.json()['source_id']}"
    ).json()
    assert detail["repository_id"] == first_repository["id"]
    assert detail["repository_name"] == "first"
    assert detail["relative_path"] == "src/Shared.java"
    listed = client.get(f"/api/v1/projects/{project_id}/sources").json()["items"]
    assert {item["repository_name"] for item in listed} == {"first", "second"}
    assert len(listed) == 3


@pytest.mark.parametrize("reverse", [False, True])
def test_unlocated_upload_does_not_reuse_a_folder_location(client: TestClient, reverse: bool) -> None:
    project_id = create_project(client)
    content = b"# Shared text\n\nAn immutable source.\n"
    locations = [{}, {"relative_path": "docs/shared.md"}]
    if reverse:
        locations.reverse()
    uploads = [client.post(f"/api/v1/projects/{project_id}/sources", data=location,
        files={"file": ("shared.md", content, "text/markdown")}) for location in locations]
    assert all(response.status_code == 202 for response in uploads)
    assert uploads[0].json()["source_id"] != uploads[1].json()["source_id"]
    assert uploads[0].json()["task_id"] != uploads[1].json()["task_id"]
    repeated = client.post(f"/api/v1/projects/{project_id}/sources", data=locations[1],
        files={"file": ("shared.md", content, "text/markdown")})
    assert repeated.json() == uploads[1].json()


def test_identical_folder_files_keep_searchable_paths_and_exact_chunks(client: TestClient) -> None:
    project_id = create_project(client)
    content = b"# Shared documentation\n\nBoth modules use this text.\n"
    records = []
    for path in ("module-a/README.md", "module-b/README.md"):
        response = client.post(f"/api/v1/projects/{project_id}/sources",
            data={"relative_path": path}, files={"file": ("README.md", content, "text/markdown")})
        assert response.status_code == 202
        uploaded = response.json()
        assert client.post(f"/api/v1/tasks/{uploaded['task_id']}/run").status_code == 200
        records.append(uploaded)
        sources = client.get(f"/api/v1/projects/{project_id}/sources", params={"q": path}).json()
        assert sources["total"] == 1
        assert sources["items"][0]["id"] == uploaded["source_id"]
        chunks = client.get(f"/api/v1/sources/{uploaded['source_id']}/chunks").json()["items"]
        assert chunks
        for chunk in chunks:
            exact = client.get(f"/api/v1/projects/{project_id}/sources/{uploaded['source_id']}/chunks/{chunk['id']}")
            assert exact.status_code == 200
            assert exact.json()["source_id"] == uploaded["source_id"]
    assert records[0]["source_id"] != records[1]["source_id"]
    changed = client.post(f"/api/v1/projects/{project_id}/sources", data={"relative_path": "module-a/README.md"},
        files={"file": ("README.md", content + b"\nNew revision.\n", "text/markdown")})
    assert changed.status_code == 202
    assert changed.json()["source_id"] not in {item["source_id"] for item in records}


def test_repository_upload_requires_path_and_matching_project(
    client: TestClient,
) -> None:
    first_project = create_project(client)
    second_project = create_project(client)
    repository = client.post(
        f"/api/v1/projects/{first_project}/repositories/resolve",
        json={"name": "first"},
    ).json()
    missing_path = client.post(
        f"/api/v1/projects/{first_project}/sources",
        data={"repository_id": repository["id"]},
        files={"file": ("App.java", b"class App {}", "text/x-java-source")},
    )
    assert missing_path.status_code == 422
    assert missing_path.json()["error"]["code"] == "SOURCE_REPOSITORY_PATH_REQUIRED"

    wrong_project = client.post(
        f"/api/v1/projects/{second_project}/sources",
        data={
            "repository_id": repository["id"],
            "relative_path": "src/App.java",
        },
        files={"file": ("App.java", b"class App {}", "text/x-java-source")},
    )
    assert wrong_project.status_code == 404
    assert wrong_project.json()["error"]["code"] == "SOURCE_REPOSITORY_NOT_FOUND"


@pytest.mark.parametrize(
    "relative_path",
    [
        "../decision.md",
        "/docs/decision.md",
        "C:/docs/decision.md",
        "docs/other.md",
        "docs//decision.md",
        f"{'a' * 1013}/decision.md",
    ],
)
def test_rejects_invalid_relative_path(
    client: TestClient, relative_path: str
) -> None:
    project_id = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/sources",
        data={"relative_path": relative_path},
        files={"file": ("decision.md", b"# Decision", "text/markdown")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SOURCE_PATH_INVALID"

