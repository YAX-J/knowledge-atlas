import uuid

import pytest
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


def test_code_structure_resolves_imported_field_and_type_qualified_calls(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    validator = upload_java(
        client,
        project_id,
        name="OrderValidator.java",
        relative_path="src/main/java/example/validation/OrderValidator.java",
        content=(
            "package example.validation;\n"
            "public class OrderValidator {\n"
            "    public void validate() {}\n"
            "    public static void normalize() {}\n"
            "}\n"
        ),
    )
    service = upload_java(
        client,
        project_id,
        name="OrderService.java",
        relative_path="src/main/java/example/service/OrderService.java",
        content=(
            "package example.service;\n"
            "import example.validation.OrderValidator;\n"
            "class OrderService {\n"
            "    private final OrderValidator validator;\n"
            "    OrderService(OrderValidator validator) { this.validator = validator; }\n"
            "    void create() {\n"
            "        validator.validate();\n"
            "        this.validator.validate();\n"
            "        OrderValidator.normalize();\n"
            "    }\n"
            "}\n"
        ),
    )

    structure = client.get(
        f"/api/v1/sources/{service['source_id']}/code-structure"
    ).json()

    assert [
        (item["receiver"], item["callee_name"], item["resolution"])
        for item in structure["cross_file_calls"]
    ] == [
        ("validator", "validate", "resolved"),
        ("this.validator", "validate", "resolved"),
        ("OrderValidator", "normalize", "resolved"),
    ]
    assert [
        item["line"] for item in structure["cross_file_calls"]
    ] == [7, 8, 9]
    assert {
        item["qualified_name"] for item in structure["related_methods"]
    } == {
        "example.validation.OrderValidator.validate",
        "example.validation.OrderValidator.normalize",
    }
    assert {
        (item["name"], item["start_line"], item["end_line"])
        for item in structure["related_methods"]
    } == {("validate", 3, 3), ("normalize", 4, 4)}
    assert {
        item["source_id"] for item in structure["related_methods"]
    } == {validator["source_id"]}
    target_structure = client.get(
        f"/api/v1/sources/{validator['source_id']}/code-structure"
    ).json()
    assert {
        item["id"] for item in structure["related_methods"]
    } <= {
        item["id"]
        for item in target_structure["symbols"]
        if item["kind"] == "method"
    }
    assert all(
        len(item["target_ids"]) == 1
        for item in structure["cross_file_calls"]
    )


def test_code_structure_marks_cross_file_overloads_as_ambiguous(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    upload_java(
        client,
        project_id,
        name="Validator.java",
        relative_path="src/example/Validator.java",
        content=(
            "package example;\n"
            "class Validator {\n"
            "    void validate() {}\n"
            "    void validate(String value) {}\n"
            "}\n"
        ),
    )
    consumer = upload_java(
        client,
        project_id,
        name="Consumer.java",
        relative_path="src/example/Consumer.java",
        content=(
            "package example;\n"
            "class Consumer {\n"
            "    Validator validator;\n"
            "    void run() { validator.validate(); }\n"
            "}\n"
        ),
    )

    structure = client.get(
        f"/api/v1/sources/{consumer['source_id']}/code-structure"
    ).json()

    assert len(structure["cross_file_calls"]) == 1
    call = structure["cross_file_calls"][0]
    assert call["resolution"] == "ambiguous"
    assert len(call["target_ids"]) == 2
    assert len(structure["related_methods"]) == 2


def test_code_structure_resolves_parameter_and_shadowed_field_receivers(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    field_validator = upload_java(
        client,
        project_id,
        name="FieldValidator.java",
        relative_path="src/example/FieldValidator.java",
        content=(
            "package example;\n"
            "class FieldValidator {\n"
            "    void validate() {}\n"
            "}\n"
        ),
    )
    request_validator = upload_java(
        client,
        project_id,
        name="RequestValidator.java",
        relative_path="src/example/RequestValidator.java",
        content=(
            "package example;\n"
            "class RequestValidator {\n"
            "    void validate() {}\n"
            "}\n"
        ),
    )
    consumer = upload_java(
        client,
        project_id,
        name="Consumer.java",
        relative_path="src/example/Consumer.java",
        content=(
            "package example;\n"
            "class Consumer {\n"
            "    FieldValidator validator;\n"
            "    void run(@Deprecated final RequestValidator validator) {\n"
            "        validator.validate();\n"
            "        this.validator.validate();\n"
            "    }\n"
            "}\n"
        ),
    )

    structure = client.get(
        f"/api/v1/sources/{consumer['source_id']}/code-structure"
    ).json()

    assert [
        item["receiver"] for item in structure["cross_file_calls"]
    ] == ["validator", "this.validator"]
    methods_by_id = {
        item["id"]: item for item in structure["related_methods"]
    }
    call_targets = {
        item["receiver"]: methods_by_id[item["target_ids"][0]]["source_id"]
        for item in structure["cross_file_calls"]
    }
    assert call_targets == {
        "validator": request_validator["source_id"],
        "this.validator": field_validator["source_id"],
    }


def test_code_structure_resolves_direct_method_local_receiver(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    field_validator = upload_java(
        client,
        project_id,
        name="FieldValidator.java",
        relative_path="src/example/FieldValidator.java",
        content=(
            "package example;\n"
            "class FieldValidator {\n"
            "    void validate() {}\n"
            "}\n"
        ),
    )
    local_validator = upload_java(
        client,
        project_id,
        name="Validator.java",
        relative_path="src/example/Validator.java",
        content=(
            "package example;\n"
            "class Validator {\n"
            "    void validate() {}\n"
            "}\n"
        ),
    )
    consumer = upload_java(
        client,
        project_id,
        name="Consumer.java",
        relative_path="src/example/Consumer.java",
        content=(
            "package example;\n"
            "class Consumer {\n"
            "    FieldValidator local;\n"
            "    void run() {\n"
            "        final Validator local = new Validator();\n"
            "        local.validate();\n"
            "        this.local.validate();\n"
            "    }\n"
            "}\n"
        ),
    )

    structure = client.get(
        f"/api/v1/sources/{consumer['source_id']}/code-structure"
    ).json()

    assert [
        (item["receiver"], item["callee_name"], item["line"])
        for item in structure["cross_file_calls"]
    ] == [
        ("local", "validate", 6),
        ("this.local", "validate", 7),
    ]
    methods_by_id = {
        item["id"]: item for item in structure["related_methods"]
    }
    call_targets = {
        item["receiver"]: methods_by_id[item["target_ids"][0]]["source_id"]
        for item in structure["cross_file_calls"]
    }
    assert call_targets == {
        "local": local_validator["source_id"],
        "this.local": field_validator["source_id"],
    }
    assert all(
        item["resolution"] == "resolved"
        for item in structure["cross_file_calls"]
    )


def test_code_structure_ignores_unsupported_local_receiver_forms() -> None:
    source_id = uuid.uuid4()
    related_source_id = uuid.uuid4()
    structure = analyze_java(
        (
            "package example;\n"
            "class Consumer {\n"
            "    void run() {\n"
            "        before.validate();\n"
            "        Validator before = new Validator();\n"
            "        var inferred = Validator.create();\n"
            "        inferred.validate();\n"
            "        Validator first, second;\n"
            "        second.validate();\n"
            "        if (true) {\n"
            "            var nested = Validator.create();\n"
            "            nested.validate();\n"
            "        }\n"
            "    }\n"
            "}\n"
        ),
        source_id=source_id,
        source_path="src/example/Consumer.java",
        related_sources=[
            JavaSourceInput(
                source_id=related_source_id,
                source_path="src/example/Validator.java",
                content=(
                    "package example;\n"
                    "class Validator { void validate() {} }\n"
                ),
            )
        ],
    )

    assert structure.related_methods == []
    assert structure.cross_file_calls == []


def test_code_structure_resolves_constructor_var_receivers_with_repository_scope(
    client: TestClient,
) -> None:
    project_id = create_project(client)
    repositories = [
        client.post(
            f"/api/v1/projects/{project_id}/repositories/resolve",
            json={"name": name},
        ).json()
        for name in ("app", "unrelated")
    ]
    targets = [
        upload_java(
            client, project_id,
            name="Validator.java",
            relative_path="src/example/tools/Validator.java",
            repository_id=repository["id"],
            content=(
                "package example.tools;\n"
                "class Validator<T> {\n"
                f"    // repository {repository['name']}\n"
                "    void validate() {}\n"
                "}\n"
            ),
        )
        for repository in repositories
    ]
    field_target = upload_java(
        client, project_id,
        name="FieldValidator.java",
        relative_path="src/example/FieldValidator.java",
        repository_id=repositories[0]["id"],
        content=(
            "package example;\n"
            "class FieldValidator {\n"
            "    void validate() {}\n"
            "}\n"
        ),
    )
    consumer = upload_java(
        client, project_id,
        name="Consumer.java",
        relative_path="src/example/Consumer.java",
        repository_id=repositories[0]["id"],
        content=(
            "package example;\n"
            "import example.tools.Validator;\n"
            "class Consumer {\n"
            "    FieldValidator validator;\n"
            "    void run() {\n"
            "        validator.validate();\n"
            "        final var validator =\n"
            "            new Validator<String>(helper(1, 2), \"text; )\");\n"
            "        validator.validate();\n"
            "        this.validator.validate();\n"
            "    }\n"
            "}\n"
        ),
    )
    endpoint = f"/api/v1/sources/{consumer['source_id']}/code-structure"
    response = client.get(endpoint)
    assert response.status_code == 200
    structure = response.json()
    methods = {item["id"]: item for item in structure["related_methods"]}
    assert [
        (
            call["receiver"], call["line"], call["resolution"],
            methods[call["target_ids"][0]]["source_id"],
        )
        for call in structure["cross_file_calls"]
    ] == [
        ("validator", 6, "resolved", field_target["source_id"]),
        ("validator", 9, "resolved", targets[0]["source_id"]),
        ("this.validator", 10, "resolved", field_target["source_id"]),
    ]
    assert targets[1]["source_id"] not in {
        method["source_id"] for method in structure["related_methods"]
    }
    assert client.get(endpoint).json() == structure


@pytest.mark.parametrize("initializer", [
    "new Validator()",
    "new example.Validator<>()",
    "new Validator<java.util.List<String>>(helper(1, 2))",
    'new /* note */ Validator(\"text; ) {\")',
])
def test_constructor_var_calls_preserve_exact_lines_and_targets(initializer: str) -> None:
    target_id = uuid.uuid4()
    structure = analyze_java(
        "package example;\n"
        "class Consumer {\n"
        "    void run() {\n"
        f"        var validator = {initializer};\n"
        "        validator.validate();\n"
        "    }\n"
        "}\n",
        source_id=uuid.uuid4(),
        related_sources=[JavaSourceInput(
            source_id=target_id,
            source_path="src/example/Validator.java",
            content="package example;\nclass Validator<T> {\n    void validate() {}\n}\n",
        )],
    )
    assert len(structure.cross_file_calls) == 1
    call = structure.cross_file_calls[0]
    assert (call.receiver, call.line, call.resolution) == ("validator", 5, "resolved")
    assert len(structure.related_methods) == 1
    method = structure.related_methods[0]
    assert (method.source_id, method.start_line, method.end_line) == (target_id, 3, 3)
    assert call.target_ids == [method.id]


@pytest.mark.parametrize("initializer", [
    "Factory.create()",
    "new Validator().copy()",
    "new Validator[2]",
    "(new Validator())",
    "(Validator) Factory.create()",
    "new Validator() { void extra() {} }",
    "flag ? new Validator() : new Validator()",
    "new Validator(new Object() {})",
    "new MissingType()",
])
def test_unsupported_var_initializers_do_not_fall_back_to_fields_or_type_names(
    initializer: str,
) -> None:
    structure = analyze_java(
        "package example;\n"
        "class Consumer {\n"
        "    Validator Validator;\n"
        "    void run() {\n"
        f"        var Validator = {initializer};\n"
        "        Validator.validate();\n"
        "        this.Validator.validate();\n"
        "    }\n"
        "}\n",
        source_id=uuid.uuid4(),
        related_sources=[JavaSourceInput(
            source_id=uuid.uuid4(),
            source_path="src/example/Validator.java",
            content="package example;\nclass Validator {\n    void validate() {}\n}\n",
        )],
    )
    assert [call.receiver for call in structure.cross_file_calls] == ["this.Validator"]


def test_constructor_var_is_scoped_to_its_block_and_method() -> None:
    structure = analyze_java(
        "package example;\n"
        "class Consumer {\n"
        "    void run() {\n"
        "        before.validate();\n"
        "        var before = new Validator();\n"
        "        if (true) {\n"
        "            var nested = new Validator();\n"
        "            nested.validate();\n"
        "        }\n"
        "        nested.validate();\n"
        "    }\n"
        "    void other() { before.validate(); }\n"
        "}\n",
        source_id=uuid.uuid4(),
        related_sources=[JavaSourceInput(
            source_id=uuid.uuid4(),
            source_path="src/example/Validator.java",
            content="package example;\nclass Validator {\n    void validate() {}\n}\n",
        )],
    )
    assert [
        (call.receiver, call.line) for call in structure.cross_file_calls
    ] == [("nested", 8)]


@pytest.mark.parametrize("declaration_type", ["var", "Validator"])
def test_locals_do_not_leak_loop_or_resource_bindings(declaration_type: str) -> None:
    structure = analyze_java(
        "package example;\n"
        "class Consumer {\n"
        "    void run() {\n"
        "        for (\n"
        f"            {declaration_type} loop = new Validator();\n"
        "            active; step()) { loop.validate(); }\n"
        "        loop.validate();\n"
        "        try (\n"
        f"            {declaration_type} first = new Validator();\n"
        f"            {declaration_type} resource = new Validator()\n"
        "        ) { resource.validate(); }\n"
        "        resource.validate();\n"
        "    }\n"
        "}\n",
        source_id=uuid.uuid4(),
        related_sources=[JavaSourceInput(
            source_id=uuid.uuid4(),
            source_path="src/example/Validator.java",
            content="package example;\nclass Validator {\n    void validate() {}\n}\n",
        )],
    )
    assert structure.cross_file_calls == []


@pytest.mark.parametrize("alternative", ["else", "else if (ready())"])
def test_code_structure_resolves_block_locals_and_restores_outer_fields(
    client: TestClient,
    alternative: str,
) -> None:
    project_id = create_project(client)
    targets = {
        name: upload_java(
            client, project_id,
            name=f"{name}.java",
            relative_path=f"src/example/{name}.java",
            content=(
                f"package example;\nclass {name} {{\n"
                "    void validate() {}\n}\n"
            ),
        )
        for name in ("FieldValidator", "LeftValidator", "RightValidator")
    }
    consumer = upload_java(
        client, project_id,
        name="Consumer.java",
        relative_path="src/example/Consumer.java",
        content=(
            "package example;\n"
            "class Consumer {\n"
            "    FieldValidator validator;\n"
            "    void run(FieldValidator parameter) {\n"
            "        validator.validate();\n"
            "        if (ready()) {\n"
            "            LeftValidator validator = new LeftValidator();\n"
            "            validator.validate();\n"
            "            parameter.validate();\n"
            "            this.validator.validate();\n"
            f"        }} {alternative} {{\n"
            "            final var validator = new RightValidator();\n"
            "            validator.validate();\n"
            "        }\n"
            "        validator.validate();\n"
            "    }\n"
            "}\n"
        ),
    )
    endpoint = f"/api/v1/sources/{consumer['source_id']}/code-structure"
    response = client.get(endpoint)
    assert response.status_code == 200
    result = response.json()
    methods = {method["id"]: method for method in result["related_methods"]}
    assert [
        (
            call["line"], call["receiver"], call["resolution"],
            methods[call["target_ids"][0]]["source_id"],
        )
        for call in result["cross_file_calls"]
    ] == [
        (5, "validator", "resolved", targets["FieldValidator"]["source_id"]),
        (8, "validator", "resolved", targets["LeftValidator"]["source_id"]),
        (9, "parameter", "resolved", targets["FieldValidator"]["source_id"]),
        (10, "this.validator", "resolved", targets["FieldValidator"]["source_id"]),
        (13, "validator", "resolved", targets["RightValidator"]["source_id"]),
        (15, "validator", "resolved", targets["FieldValidator"]["source_id"]),
    ]
    assert client.get(endpoint).json() == result


@pytest.mark.parametrize("header", ["{", "if (ready()) {", "while (active) {"])
def test_unknown_nested_var_shadows_only_inside_its_own_block(header: str) -> None:
    result = analyze_java(
        "package example;\n"
        "class Consumer {\n"
        "    Validator validator;\n"
        "    void run() {\n"
        "        validator.validate();\n"
        f"        {header}\n"
        "            var validator = Factory.create();\n"
        "            validator.validate();\n"
        "            this.validator.validate();\n"
        "        }\n"
        "        validator.validate();\n"
        "    }\n"
        "}\n",
        source_id=uuid.uuid4(),
        related_sources=[JavaSourceInput(
            source_id=uuid.uuid4(), source_path="src/example/Validator.java",
            content="package example;\nclass Validator {\n    void validate() {}\n}\n",
        )],
    )
    assert [
        (call.line, call.receiver) for call in result.cross_file_calls
    ] == [(5, "validator"), (9, "this.validator"), (11, "validator")]


def test_nested_calls_keep_ancestor_bindings_after_sibling_blocks_close() -> None:
    result = analyze_java(
        "package example;\n"
        "class Consumer {\n"
        "    void run() {\n"
        "        {\n"
        "            Validator shared = new Validator();\n"
        "            while (ready()) {\n"
        "                {\n"
        "                    var leaf = new Validator();\n"
        "                    leaf.validate();\n"
        "                }\n"
        "                shared.validate();\n"
        "            }\n"
        "            shared.validate();\n"
        "        }\n"
        "        shared.validate();\n"
        "    }\n"
        "}\n",
        source_id=uuid.uuid4(),
        related_sources=[JavaSourceInput(
            source_id=uuid.uuid4(), source_path="src/example/Validator.java",
            content="package example;\nclass Validator {\n    void validate() {}\n}\n",
        )],
    )
    assert [
        (call.line, call.receiver) for call in result.cross_file_calls
    ] == [(9, "leaf"), (11, "shared"), (13, "shared")]


@pytest.mark.parametrize("excluded_body", [
    "for (var validator = create(); active; step()) {\n"
    "    validator.validate();\n}",
    "try (var validator = create()) {\n    validator.validate();\n}",
    "try {} catch (@Marker Exception validator) {\n    validator.validate();\n}",
    "Runnable action = () -> {\n    validator.validate();\n};",
    "Runnable action = () -> {\n"
    "    for (Validator validator : items) {\n"
    "        validator.validate();\n    }\n};",
    "Runnable action = () -> {\n"
    "    try { validator.validate(); }\n"
    "    catch (Validator validator) { validator.validate(); }\n"
    "    finally { validator.validate(); }\n};",
    "Object action = new Object() {\n"
    "    void run() {\n        this.validator.validate();\n    }\n};",
    "class Local {\n    void run() {\n        validator.validate();\n    }\n}",
    "switch (value) {\n    case 1: validator.validate(); break;\n}",
    "if (value instanceof Validator validator) {\n    validator.validate();\n}",
    "for (Item validator : items) {\n    {\n        validator.validate();\n    }\n}",
])
def test_excluded_scopes_do_not_guess_outer_receivers(excluded_body: str) -> None:
    result = analyze_java(
        "package example;\n"
        "class Consumer {\n"
        "    Validator validator;\n"
        "    void run() {\n"
        f"        {excluded_body}\n"
        "        this.validator.validate();\n"
        "    }\n"
        "}\n",
        source_id=uuid.uuid4(),
        related_sources=[JavaSourceInput(
            source_id=uuid.uuid4(), source_path="src/example/Validator.java",
            content="package example;\nclass Validator {\n    void validate() {}\n}\n",
        )],
    )
    assert [call.receiver for call in result.cross_file_calls] == ["this.validator"]


@pytest.mark.parametrize("declaration", [
    "Validator validator",
    "final example.Validator<String> validator",
    "example.Validator<java.util.Map<String[], Integer>> validator",
    "final\n            Validator<String>\n            validator",
])
def test_code_structure_resolves_enhanced_for_receivers_and_restores_fields(
    client: TestClient,
    declaration: str,
) -> None:
    project_id = create_project(client)
    targets = {
        name: upload_java(
            client, project_id,
            name=f"{name}.java", relative_path=f"src/example/{name}.java",
            content=(f"package example;\nclass {name} {{\n"
                     "    void validate() {}\n"
                     + ("    Iterable<Validator> values() { return null; }\n"
                        if name == "FieldValidator" else "")
                     + "}\n"),
        )
        for name in ("FieldValidator", "Validator")
    }
    content = (
        "package example;\nclass Consumer {\n"
        "    FieldValidator validator;\n    void run() {\n"
        "        validator.validate();\n"
        f"        for ({declaration} : validator.values()) {{\n"
        "            validator.validate();\n"
        "            this.validator.validate();\n"
        "            if (ready()) {\n"
        "                var helper = new Validator();\n"
        "                helper.validate();\n"
        "            }\n"
        "        }\n"
        "        validator.validate();\n"
        "        helper.validate();\n"
        "    }\n}\n"
    )
    consumer = upload_java(
        client, project_id, name="Consumer.java",
        relative_path="src/example/Consumer.java", content=content,
    )
    endpoint = f"/api/v1/sources/{consumer['source_id']}/code-structure"
    response = client.get(endpoint)
    assert response.status_code == 200
    result = response.json()
    methods = {method["id"]: method for method in result["related_methods"]}
    extra_lines = declaration.count("\n")
    assert [
        (call["line"], call["receiver"], call["resolution"],
         methods[call["target_ids"][0]]["source_id"])
        for call in result["cross_file_calls"]
    ] == [
        (5, "validator", "resolved", targets["FieldValidator"]["source_id"]),
        (7 + extra_lines, "validator", "resolved", targets["Validator"]["source_id"]),
        (8 + extra_lines, "this.validator", "resolved", targets["FieldValidator"]["source_id"]),
        (11 + extra_lines, "helper", "resolved", targets["Validator"]["source_id"]),
        (14 + extra_lines, "validator", "resolved", targets["FieldValidator"]["source_id"]),
    ]
    assert client.get(endpoint).json() == result


@pytest.mark.parametrize("declaration", [
    "var Validator", "Validator[] Validator", "Validator Validator[]",
])
def test_unknown_enhanced_for_elements_do_not_fall_back_to_fields_or_types(
    declaration: str,
) -> None:
    result = analyze_java(
        "package example;\nclass Consumer {\n"
        "    Validator Validator;\n    void run(Validator parameter) {\n"
        f"        for ({declaration} : items) {{\n"
        "            Validator.validate();\n"
        "            this.Validator.validate();\n"
        "            parameter.validate();\n"
        "        }\n"
        "        Validator.validate();\n"
        "    }\n}\n",
        source_id=uuid.uuid4(),
        related_sources=[JavaSourceInput(
            source_id=uuid.uuid4(), source_path="src/example/Validator.java",
            content="package example;\nclass Validator {\n    void validate() {}\n}\n",
        )],
    )
    assert [(call.line, call.receiver) for call in result.cross_file_calls] == [
        (7, "this.Validator"), (8, "parameter"), (10, "Validator"),
    ]


def test_enhanced_for_bindings_are_isolated_between_nested_and_sibling_loops() -> None:
    result = analyze_java(
        "package example;\nclass Consumer {\n    void run() {\n"
        "        for (Validator outer : items) {\n"
        "            for (Validator inner : others) {\n"
        "                outer.validate();\n"
        "                inner.validate();\n"
        "            }\n"
        "            outer.validate();\n"
        "            inner.validate();\n"
        "        }\n"
        "        for (Other outer : others) {\n"
        "            outer.validate();\n"
        "        }\n"
        "        outer.validate();\n"
        "    }\n}\n",
        source_id=uuid.uuid4(),
        related_sources=[JavaSourceInput(
            source_id=uuid.uuid4(), source_path=f"src/example/{name}.java",
            content=(f"package example;\nclass {name} {{\n"
                     "    void validate() {}\n}\n"),
        ) for name in ("Validator", "Other")],
    )
    methods = {method.id: method for method in result.related_methods}
    assert [
        (call.line, call.receiver, methods[call.target_ids[0]].owner_qualified_name)
        for call in result.cross_file_calls
    ] == [
        (6, "outer", "example.Validator"),
        (7, "inner", "example.Validator"),
        (9, "outer", "example.Validator"),
        (13, "outer", "example.Other"),
    ]


@pytest.mark.parametrize("header", [
    "for (Validator item = create(); active; step())",
    "for (@Marker Validator item : items)",
])
def test_unsupported_for_headers_keep_body_calls_excluded(header: str) -> None:
    result = analyze_java(
        "package example;\nclass Consumer {\n"
        "    Validator item;\n    void run() {\n"
        f"        {header} {{\n            item.validate();\n        }}\n"
        "        item.validate();\n    }\n}\n",
        source_id=uuid.uuid4(),
        related_sources=[JavaSourceInput(
            source_id=uuid.uuid4(), source_path="src/example/Validator.java",
            content="package example;\nclass Validator {\n    void validate() {}\n}\n",
        )],
    )
    assert [(call.line, call.receiver) for call in result.cross_file_calls] == [(8, "item")]


@pytest.mark.parametrize("declaration", [
    "Failure failure",
    "final example.Failure failure",
    "final\n            example.Failure\n            failure",
    "/* parameter */ Failure /* name */ failure",
])
def test_code_structure_resolves_exception_scopes_with_exact_lines_and_stable_ids(
    client: TestClient,
    declaration: str,
) -> None:
    project_id = create_project(client)
    targets = {
        name: upload_java(
            client, project_id,
            name=f"{name}.java", relative_path=f"src/example/{name}.java",
            content=(
                f"package example;\nclass {name}"
                + (" extends Exception" if name != "Handler" else "")
                + " {\n    void handle() {}\n}\n"
            ),
        )
        for name in ("Handler", "Failure", "OtherFailure")
    }
    consumer = upload_java(
        client, project_id, name="Consumer.java",
        relative_path="src/example/Consumer.java",
        content=(
            "package example;\nclass Consumer {\n"
            "    Handler failure;\n    void run() {\n"
            "        try {\n"
            "            var temporary = new Handler();\n"
            "            temporary.handle();\n"
            "            failure.handle();\n"
            f"        }} catch ({declaration}) {{\n"
            "            failure.handle();\n"
            "            this.failure.handle();\n"
            "            if (ready()) {\n"
            "                failure.handle();\n"
            "            }\n"
            "            temporary.handle();\n"
            "        } catch (OtherFailure failure) {\n"
            "            failure.handle();\n"
            "        } finally {\n"
            "            var cleanup = new Handler();\n"
            "            cleanup.handle();\n"
            "            failure.handle();\n"
            "            temporary.handle();\n"
            "        }\n"
            "        failure.handle();\n"
            "        cleanup.handle();\n"
            "    }\n}\n"
        ),
    )
    endpoint = f"/api/v1/sources/{consumer['source_id']}/code-structure"
    response = client.get(endpoint)
    assert response.status_code == 200
    result = response.json()
    methods = {method["id"]: method for method in result["related_methods"]}
    extra_lines = declaration.count("\n")
    expected = [
        (7, "temporary", "Handler"),
        (8, "failure", "Handler"),
        (10 + extra_lines, "failure", "Failure"),
        (11 + extra_lines, "this.failure", "Handler"),
        (13 + extra_lines, "failure", "Failure"),
        (17 + extra_lines, "failure", "OtherFailure"),
        (20 + extra_lines, "cleanup", "Handler"),
        (21 + extra_lines, "failure", "Handler"),
        (24 + extra_lines, "failure", "Handler"),
    ]
    assert [
        (call["line"], call["receiver"], call["resolution"],
         methods[call["target_ids"][0]]["source_id"])
        for call in result["cross_file_calls"]
    ] == [
        (line, receiver, "resolved", targets[name]["source_id"])
        for line, receiver, name in expected
    ]
    assert client.get(endpoint).json() == result


@pytest.mark.parametrize("declaration", [
    "Failure | OtherFailure Failure",
    "final example.OtherFailure | example.Failure Failure",
    "Missing | OtherFailure Failure",
    "ExternalFailure Failure",
])
def test_unknown_catch_receivers_do_not_fall_back_to_fields_or_types(
    declaration: str,
) -> None:
    result = analyze_java(
        "package example;\nclass Consumer {\n"
        "    Handler Failure;\n    void run(Handler parameter) {\n"
        f"        try {{}} catch ({declaration}) {{\n"
        "            Failure.handle();\n"
        "            this.Failure.handle();\n"
        "            parameter.handle();\n"
        "        } finally {\n"
        "            Failure.handle();\n"
        "        }\n"
        "        Failure.handle();\n    }\n}\n",
        source_id=uuid.uuid4(),
        related_sources=[JavaSourceInput(
            source_id=uuid.uuid4(), source_path=f"src/example/{name}.java",
            content=f"package example;\nclass {name} {{\n    void handle() {{}}\n}}\n",
        ) for name in ("Handler", "Failure", "OtherFailure")],
    )
    methods = {method.id: method for method in result.related_methods}
    assert [(call.line, call.receiver) for call in result.cross_file_calls] == [
        (7, "this.Failure"), (8, "parameter"), (10, "Failure"), (12, "Failure"),
    ]
    assert all(
        methods[target].owner_qualified_name == "example.Handler"
        for call in result.cross_file_calls for target in call.target_ids
    )


def test_catch_inside_enhanced_for_retains_loop_binding_without_leaking_parameter() -> None:
    result = analyze_java(
        "package example;\nclass Consumer {\n    void run() {\n"
        "        for (Handler item : items) {\n"
        "            try {} catch (Failure failure) {\n"
        "                item.handle();\n"
        "                failure.handle();\n"
        "            }\n"
        "            item.handle();\n"
        "            failure.handle();\n"
        "        }\n    }\n}\n",
        source_id=uuid.uuid4(),
        related_sources=[JavaSourceInput(
            source_id=uuid.uuid4(), source_path=f"src/example/{name}.java",
            content=f"package example;\nclass {name} {{\n    void handle() {{}}\n}}\n",
        ) for name in ("Handler", "Failure")],
    )
    methods = {method.id: method for method in result.related_methods}
    assert [
        (call.line, call.receiver, methods[call.target_ids[0]].owner_qualified_name)
        for call in result.cross_file_calls
    ] == [
        (6, "item", "example.Handler"),
        (7, "failure", "example.Failure"),
        (9, "item", "example.Handler"),
    ]


def test_resource_try_stays_excluded_but_catch_and_finally_restore_outer_bindings() -> None:
    result = analyze_java(
        "package example;\nclass Consumer {\n"
        "    Handler resource;\n    void run() {\n"
        "        try (\n"
        "            Resource resource = new Resource();\n"
        "            var other = new Resource()\n"
        "        ) {\n"
        "            resource.handle();\n"
        "            this.resource.handle();\n"
        "        } catch (Failure failure) {\n"
        "            failure.handle();\n"
        "            resource.handle();\n"
        "            other.handle();\n"
        "        } finally {\n"
        "            resource.handle();\n"
        "            failure.handle();\n"
        "            other.handle();\n"
        "        }\n"
        "        resource.handle();\n    }\n}\n",
        source_id=uuid.uuid4(),
        related_sources=[JavaSourceInput(
            source_id=uuid.uuid4(), source_path=f"src/example/{name}.java",
            content=f"package example;\nclass {name} {{\n    void handle() {{}}\n}}\n",
        ) for name in ("Handler", "Resource", "Failure")],
    )
    methods = {method.id: method for method in result.related_methods}
    assert [
        (call.line, call.receiver, methods[call.target_ids[0]].owner_qualified_name)
        for call in result.cross_file_calls
    ] == [
        (12, "failure", "example.Failure"),
        (13, "resource", "example.Handler"),
        (16, "resource", "example.Handler"),
        (20, "resource", "example.Handler"),
    ]


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
        content="package example;\ninterface HiddenPort { void ping(); }\n",
        parse=False,
    )
    other_project_id = create_project(client)
    upload_java(
        client,
        other_project_id,
        name="ForeignPort.java",
        relative_path="src/ForeignPort.java",
        content="package example;\ninterface ForeignPort { void ping(); }\n",
    )
    consumer = upload_java(
        client,
        project_id,
        name="Consumer.java",
        relative_path="src/Consumer.java",
        content=(
            "package example;\n"
            "class Consumer implements HiddenPort, ForeignPort {\n"
            "    HiddenPort hidden;\n"
            "    ForeignPort foreign;\n"
            "    void run() { hidden.ping(); foreign.ping(); }\n"
            "}\n"
        ),
    )

    structure = client.get(
        f"/api/v1/sources/{consumer['source_id']}/code-structure"
    ).json()

    assert structure["type_relationships"] == []
    assert structure["related_types"] == []
    assert structure["related_methods"] == []
    assert structure["cross_file_calls"] == []
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
    assert structure["related_methods"] == []
    assert structure["cross_file_calls"] == []
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
        content="package example;\ninterface Port { void ping(); }\n",
        repository_id=first_repository["id"],
    )
    consumer = upload_java(
        client,
        project_id,
        name="Consumer.java",
        relative_path="src/Consumer.java",
        content=(
            "package example;\n"
            "class Consumer implements Port {\n"
            "    Port port;\n"
            "    public void ping() {}\n"
            "    void run() { port.ping(); }\n"
            "}\n"
        ),
        repository_id=second_repository["id"],
    )

    structure = client.get(
        f"/api/v1/sources/{consumer['source_id']}/code-structure"
    ).json()

    assert structure["related_types"] == []
    assert structure["type_relationships"] == []
    assert structure["related_methods"] == []
    assert structure["cross_file_calls"] == []


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
    assert structure.related_methods == []
    assert structure.cross_file_calls == []
    assert structure.truncated is True
