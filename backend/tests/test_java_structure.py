import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.domain import SourceDocument, SourceStatus
from app.services import ingestion
from app.services.java_source import JavaSourceInput, analyze_java
from tests.test_sources import create_project


def upload_java(
    client: TestClient,
    project_id: str,
    *,
    name: str,
    content: str,
    relative_path: str,
    parse: bool = True,
    repository_id: str | None = None,
) -> dict:
    data = {"source_type": "java", "relative_path": relative_path}
    if repository_id is not None:
        data["repository_id"] = repository_id
    response = client.post(
        f"/api/v1/projects/{project_id}/sources",
        data=data,
        files={"file": (name, content.encode("utf-8"), "text/x-java-source")},
    )
    assert response.status_code == 202
    result = response.json()
    if parse:
        task = client.post(f"/api/v1/tasks/{result['task_id']}/run")
        assert task.status_code == 200
        assert task.json()["status"] == "succeeded"
    return result


def test_code_structure_resolves_project_java_inheritance(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    port = upload_java(
        client,
        project_id,
        name="OrderPort.java",
        relative_path="sample/src/main/java/example/api/OrderPort.java",
        content="package example.api;\npublic interface OrderPort {}\n",
    )
    base = upload_java(
        client,
        project_id,
        name="BaseService.java",
        relative_path="sample/src/main/java/example/service/BaseService.java",
        content="package example.service;\npublic class BaseService {}\n",
    )
    service = upload_java(
        client,
        project_id,
        name="OrderService.java",
        relative_path="sample/src/main/java/example/service/OrderService.java",
        content=(
            "package example.service;\n"
            "import example.api.*;\n"
            "import java.io.Serializable;\n"
            "public class OrderService extends BaseService implements OrderPort, Serializable {\n"
            "    void create() { validate(); }\n"
            "    void validate() {}\n"
            "}\n"
        ),
    )

    response = client.get(
        f"/api/v1/sources/{service['source_id']}/code-structure"
    )

    assert response.status_code == 200
    structure = response.json()
    assert [item["kind"] for item in structure["type_relationships"]] == [
        "extends",
        "implements",
    ]
    assert {
        item["qualified_name"] for item in structure["related_types"]
    } == {"example.api.OrderPort", "example.service.BaseService"}
    assert {
        item["source_id"] for item in structure["related_types"]
    } == {port["source_id"], base["source_id"]}
    assert {
        item["source_path"] for item in structure["related_types"]
    } == {
        "sample/src/main/java/example/api/OrderPort.java",
        "sample/src/main/java/example/service/BaseService.java",
    }
    assert all(
        item["resolution"] == "resolved"
        for item in structure["type_relationships"]
    )
    assert all(item["line"] == 4 for item in structure["type_relationships"])
    assert len(structure["calls"]) == 1
    assert structure["calls"][0]["callee_name"] == "validate"
    assert structure["truncated"] is False


def test_code_structure_marks_duplicate_project_type_as_ambiguous(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    first = upload_java(
        client,
        project_id,
        name="Port.java",
        relative_path="one/example/api/Port.java",
        content="package example.api;\npublic interface Port {}\n",
    )
    second = upload_java(
        client,
        project_id,
        name="Port.java",
        relative_path="two/example/api/Port.java",
        content="package example.api;\n// duplicate source tree\npublic interface Port {}\n",
    )
    consumer = upload_java(
        client,
        project_id,
        name="Consumer.java",
        relative_path="app/example/Consumer.java",
        content=(
            "package example;\n"
            "import example.api.Port;\n"
            "class Consumer implements Port {}\n"
        ),
    )

    structure = client.get(
        f"/api/v1/sources/{consumer['source_id']}/code-structure"
    ).json()

    assert len(structure["type_relationships"]) == 1
    relationship = structure["type_relationships"][0]
    assert relationship["resolution"] == "ambiguous"
    assert len(relationship["target_ids"]) == 2
    assert {
        item["source_id"] for item in structure["related_types"]
    } == {first["source_id"], second["source_id"]}


def test_code_structure_ignores_unready_and_other_project_types(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = create_project(client)
    unready = upload_java(
        client,
        project_id,
        name="HiddenPort.java",
        relative_path="src/HiddenPort.java",
        content="package example;\ninterface HiddenPort {}\n",
        parse=False,
    )
    other_project_id = create_project(client)
    upload_java(
        client,
        other_project_id,
        name="ForeignPort.java",
        relative_path="src/ForeignPort.java",
        content="package example;\ninterface ForeignPort {}\n",
    )
    consumer = upload_java(
        client,
        project_id,
        name="Consumer.java",
        relative_path="src/Consumer.java",
        content=(
            "package example;\n"
            "class Consumer implements HiddenPort, ForeignPort {}\n"
        ),
    )

    structure = client.get(
        f"/api/v1/sources/{consumer['source_id']}/code-structure"
    ).json()

    assert structure["type_relationships"] == []
    assert structure["related_types"] == []
    source = db_session.get(SourceDocument, uuid.UUID(unready["source_id"]))
    assert source is not None
    assert source.status == SourceStatus.UPLOADED


def test_code_structure_requires_ready_java_source(client: TestClient) -> None:
    project_id = create_project(client)
    unready = upload_java(
        client,
        project_id,
        name="Pending.java",
        relative_path="src/Pending.java",
        content="class Pending {}\n",
        parse=False,
    )
    response = client.get(
        f"/api/v1/sources/{unready['source_id']}/code-structure"
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SOURCE_NOT_PARSED"


def test_code_structure_reports_related_source_byte_limit(
    client: TestClient,
    monkeypatch,
) -> None:
    project_id = create_project(client)
    upload_java(
        client,
        project_id,
        name="Base.java",
        relative_path="src/Base.java",
        content="package example;\nclass Base {}\n",
    )
    consumer = upload_java(
        client,
        project_id,
        name="Consumer.java",
        relative_path="src/Consumer.java",
        content="package example;\nclass Consumer extends Base {}\n",
    )
    monkeypatch.setattr(ingestion, "MAX_RELATED_JAVA_BYTES", 1)

    structure = client.get(
        f"/api/v1/sources/{consumer['source_id']}/code-structure"
    ).json()

    assert structure["related_types"] == []
    assert structure["type_relationships"] == []
    assert structure["truncated"] is True


def test_code_structure_does_not_cross_repository_boundary(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    first_repository = client.post(
        f"/api/v1/projects/{project_id}/repositories/resolve",
        json={"name": "first"},
    ).json()
    second_repository = client.post(
        f"/api/v1/projects/{project_id}/repositories/resolve",
        json={"name": "second"},
    ).json()
    upload_java(
        client,
        project_id,
        name="Port.java",
        relative_path="src/Port.java",
        content="package example;\ninterface Port {}\n",
        repository_id=first_repository["id"],
    )
    consumer = upload_java(
        client,
        project_id,
        name="Consumer.java",
        relative_path="src/Consumer.java",
        content="package example;\nclass Consumer implements Port {}\n",
        repository_id=second_repository["id"],
    )

    structure = client.get(
        f"/api/v1/sources/{consumer['source_id']}/code-structure"
    ).json()

    assert structure["related_types"] == []
    assert structure["type_relationships"] == []


def test_code_structure_does_not_reference_truncated_source_symbols() -> None:
    source_id = uuid.uuid4()
    base_source_id = uuid.uuid4()
    content = "\n".join(
        [f"class Visible{index} {{}}" for index in range(200)]
        + ["class Hidden extends Base {}"]
    )

    structure = analyze_java(
        content,
        source_id=source_id,
        source_path="src/ManyTypes.java",
        related_sources=[
            JavaSourceInput(
                source_id=base_source_id,
                source_path="src/Base.java",
                content="class Base {}\n",
            )
        ],
    )

    assert len(structure.symbols) == 200
    assert structure.related_types == []
    assert structure.type_relationships == []
    assert structure.truncated is True
