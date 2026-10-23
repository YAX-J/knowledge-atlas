"""Factory-initialized loop/resources keep ordered, body-only receiver bindings."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.services.java_source import JavaSourceInput, analyze_java
from tests.test_java_structure import upload_java
from tests.test_java_v1 import analyze, source, targets
from tests.test_sources import create_project


RESOURCE = source("Resource", "public class Resource {\n    public void ping() {}\n}", "model")
FIELD = source("Field", "class Field {\n    void ping() {}\n}")
FACTORY = source(
    "Factory", "public class Factory {\n"
    "    public static model.Resource open(String... args) { return null; }\n}", "tools",
)


@pytest.mark.parametrize("header", [
    "for (var value = Factory.open(); value.active(); value.step())",
    'for (final var value = Factory.open("a", "b"); active; step())',
    "try (var value = Factory.open())",
    "try (final var value = Factory.open();)",
])
def test_qualified_header_factory_binds_body_and_restores_field(header: str) -> None:
    result = analyze(
        "import tools.Factory;\nclass Consumer {\n    Field value;\n    void run() {\n"
        f"        {header} {{\n            value.ping();\n        }}\n"
        "        value.ping();\n    }\n}\n", FACTORY, RESOURCE, FIELD,
    )
    assert targets(result) == [
        ("value", "resolved", ["model.Resource.ping"]),
        ("value", "resolved", ["example.Field.ping"]),
    ]
    assert all(call.callee_name != "open" for call in result.cross_file_calls)


@pytest.mark.parametrize("import_name", ["tools.Factory.open", "tools.Factory.*"])
def test_static_import_factory_header_retains_exact_original_method(import_name: str) -> None:
    body = (
        f"import static {import_name};\nclass Consumer {{\n    void run() {{\n"
        "        try (var value = open()) {\n            value.ping();\n        }\n    }\n}\n"
    )
    result = analyze(body, FACTORY, RESOURCE)
    assert targets(result) == [("value", "resolved", ["model.Resource.ping"])]
    assert result.cross_file_calls[0].line == 6
    original = analyze_java(RESOURCE.content, source_id=RESOURCE.source_id)
    method = next(item for item in original.symbols if item.name == "ping")
    assert result.cross_file_calls[0].target_ids == [method.id]
    assert analyze(body, FACTORY, RESOURCE) == result


def test_private_current_factory_header_precedes_static_import() -> None:
    result = analyze(
        "import static tools.Factory.*;\nclass Consumer {\n"
        "    private static Field open() { return null; }\n    void run() {\n"
        "        try (var value = open()) {\n            value.ping();\n        }\n    }\n}\n",
        FACTORY, RESOURCE, FIELD,
    )
    assert targets(result) == [("value", "resolved", ["example.Field.ping"])]
    assert result.calls == []


def test_inherited_factory_header_uses_declaring_return_type_context() -> None:
    base = source(
        "Base", "import model.Resource;\nclass Base {\n"
        "    static Resource open() { return null; }\n}",
    )
    result = analyze(
        "class Consumer extends Base {\n    void run() {\n"
        "        for (var value = open(); active; step()) {\n"
        "            value.ping();\n        }\n    }\n}\n", base, RESOURCE,
    )
    assert targets(result) == [("value", "resolved", ["model.Resource.ping"])]


def test_resource_header_factory_does_not_leak_into_catch_finally_or_siblings() -> None:
    result = analyze(
        "import tools.Factory;\nclass Consumer {\n    Field value;\n    void run() {\n"
        "        try (var value = Factory.open()) {\n            value.ping();\n"
        "        } catch (Exception error) {\n            value.ping();\n"
        "        } finally {\n            value.ping();\n        }\n"
        "        {\n            value.ping();\n        }\n    }\n}\n",
        FACTORY, RESOURCE, FIELD,
    )
    assert targets(result) == [
        ("value", "resolved", ["model.Resource.ping"]),
        ("value", "resolved", ["example.Field.ping"]),
        ("value", "resolved", ["example.Field.ping"]),
        ("value", "resolved", ["example.Field.ping"]),
    ]


@pytest.mark.parametrize("resources, expected", [
    ("var value = Factory.open(); var Factory = external()", ["model.Resource.ping"]),
    ("var Factory = external(); var value = Factory.open()", []),
    ("var Factory = new Object(); var value = Factory.open()", []),
])
def test_resource_factory_qualifiers_follow_declaration_order(resources: str, expected: list[str]) -> None:
    result = analyze(
        "import tools.Factory;\nclass Consumer {\n    void run() {\n"
        f"        try ({resources}) {{\n            value.ping();\n        }}\n    }}\n}}\n",
        FACTORY, RESOURCE,
    )
    assert targets(result) == ([("value", "resolved", expected)] if expected else [])


@pytest.mark.parametrize("prefix, parameter, before", [
    ("", "Object Factory", ""),
    ("    Object Factory;\n", "", ""),
    ("", "", "        var Factory = external();\n"),
    ("", "", "        Object Factory = external();\n"),
])
def test_outer_bindings_shadow_header_factory_type(prefix: str, parameter: str, before: str) -> None:
    result = analyze(
        "import tools.Factory;\nclass Consumer {\n"
        f"{prefix}    void run({parameter}) {{\n{before}"
        "        try (var value = Factory.open()) {\n            value.ping();\n        }\n    }\n}\n",
        FACTORY, RESOURCE,
    )
    assert result.cross_file_calls == []


def test_header_binding_is_available_before_inferencing_body_locals() -> None:
    result = analyze(
        "import tools.Factory;\nclass Consumer {\n    void run() {\n"
        "        try (var Factory = external()) {\n"
        "            var value = Factory.open();\n            value.ping();\n        }\n    }\n}\n",
        FACTORY, RESOURCE,
    )
    assert result.cross_file_calls == []


@pytest.mark.parametrize("initializer", [
    "missing()", "Factory.open().copy()", "(Factory.open())", "flag ? Factory.open() : Factory.open()",
])
def test_unknown_header_factory_still_shadows_field(initializer: str) -> None:
    result = analyze(
        "import tools.Factory;\nclass Consumer {\n    Field value;\n    void run() {\n"
        f"        try (var value = {initializer}) {{\n"
        "            value.ping();\n            this.value.ping();\n        }\n    }\n}\n",
        FACTORY, RESOURCE, FIELD,
    )
    assert targets(result) == [("this.value", "resolved", ["example.Field.ping"])]


def test_conflicting_header_factory_returns_do_not_choose_one() -> None:
    factory = source(
        "Factory", "public class Factory {\n"
        "    public static model.Resource open(int value) { return null; }\n"
        "    public static example.Field open(String value) { return null; }\n}", "tools",
    )
    result = analyze(
        "import tools.Factory;\nclass Consumer {\n    void run() {\n"
        "        try (var value = Factory.open(1)) {\n            value.ping();\n        }\n    }\n}\n",
        factory, RESOURCE, FIELD,
    )
    assert result.cross_file_calls == []


def test_header_factory_keeps_resolved_default_package_return_identity() -> None:
    local_resource = JavaSourceInput(
        uuid.uuid4(), "Resource.java", "class Resource {\n    void ping() {}\n}\n",
    )
    factory = JavaSourceInput(
        uuid.uuid4(), "Factory.java", "class Factory {\n    static Resource open() { return null; }\n}\n",
    )
    result = analyze_java(
        "import model.Resource;\nclass Consumer {\n    void run() {\n"
        "        try (var value = Factory.open()) {\n            value.ping();\n        }\n    }\n}\n",
        source_id=uuid.uuid4(), related_sources=[local_resource, factory, RESOURCE],
    )
    assert {method.source_id for method in result.related_methods} == {local_resource.source_id}


def test_duplicate_header_return_versions_keep_original_ambiguity() -> None:
    updated = source(
        "Resource", "public class Resource {\n    public void ping() { changed(); }\n}", "model",
    )
    result = analyze(
        "import tools.Factory;\nclass Consumer {\n    void run() {\n"
        "        try (var value = Factory.open()) {\n            value.ping();\n        }\n    }\n}\n",
        FACTORY, RESOURCE, updated,
    )
    assert targets(result) == [("value", "ambiguous", ["model.Resource.ping"] * 2)]


def test_incomplete_member_lookup_suppresses_header_factory_import_fallback() -> None:
    base = source("Base", "class Base extends Base {}")
    result = analyze(
        "import static tools.Factory.*;\nclass Consumer extends Base {\n    void run() {\n"
        "        try (var value = open()) {\n            value.ping();\n        }\n    }\n}\n",
        base, FACTORY, RESOURCE,
    )
    assert result.truncated
    assert result.cross_file_calls == []


def test_classic_for_header_calls_stay_omitted_and_nested_factories_do_not_leak() -> None:
    result = analyze(
        "import tools.Factory;\nclass Consumer {\n    Field value;\n    void run() {\n"
        "        for (var value = Factory.open(); value.ping(); value.ping()) {\n"
        "            value.ping();\n            try (var inner = Factory.open()) {\n"
        "                inner.ping();\n            }\n            inner.ping();\n        }\n"
        "        value.ping();\n    }\n}\n", FACTORY, RESOURCE, FIELD,
    )
    assert targets(result) == [
        ("value", "resolved", ["model.Resource.ping"]),
        ("inner", "resolved", ["model.Resource.ping"]),
        ("value", "resolved", ["example.Field.ping"]),
    ]


def test_api_header_factory_waits_for_same_repository_ready_declarations(client: TestClient) -> None:
    project = create_project(client)
    repository = client.post(
        f"/api/v1/projects/{project}/repositories/resolve", json={"name": "app"},
    ).json()["id"]
    unrelated = client.post(
        f"/api/v1/projects/{project}/repositories/resolve", json={"name": "unrelated"},
    ).json()["id"]
    upload_java(
        client, project, name="Factory.java", relative_path=FACTORY.source_path,
        content=FACTORY.content, repository_id=unrelated,
    )
    factory = upload_java(
        client, project, name="Factory.java", relative_path=FACTORY.source_path,
        content=FACTORY.content, repository_id=repository, parse=False,
    )
    resource = upload_java(
        client, project, name="Resource.java", relative_path=RESOURCE.source_path,
        content=RESOURCE.content, repository_id=repository,
    )
    consumer = upload_java(
        client, project, name="Consumer.java", relative_path="src/example/Consumer.java",
        repository_id=repository, content="package example;\nimport tools.Factory;\nclass Consumer {\n"
        "    void run() {\n        try (var value = Factory.open()) {\n"
        "            value.ping();\n        }\n    }\n}\n",
    )
    endpoint = f"/api/v1/sources/{consumer['source_id']}/code-structure"
    assert client.get(endpoint).json()["cross_file_calls"] == []
    assert client.post(f"/api/v1/tasks/{factory['task_id']}/run").json()["status"] == "succeeded"
    result = client.get(endpoint).json()
    assert [(call["receiver"], call["line"]) for call in result["cross_file_calls"]] == [("value", 6)]
    assert {method["source_id"] for method in result["related_methods"]} == {resource["source_id"]}
    assert client.get(endpoint).json() == result
