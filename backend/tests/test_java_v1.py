"""Integrated acceptance for the bounded repository-local Java analysis V1."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.services import java_source
from app.services.java_source import JavaSourceInput, analyze_java
from tests.test_java_structure import upload_java
from tests.test_sources import create_project


def source(name: str, body: str, package: str = "example") -> JavaSourceInput:
    return JavaSourceInput(
        source_id=uuid.uuid5(uuid.NAMESPACE_URL, name + body + package),
        source_path=f"src/{package.replace('.', '/')}/{name}.java",
        content=f"package {package};\n{body}\n",
    )


def analyze(body: str, *related: JavaSourceInput):
    return analyze_java(
        "package example;\n" + body,
        source_id=uuid.uuid5(uuid.NAMESPACE_URL, body),
        related_sources=list(related),
    )


def targets(result):
    methods = {method.id: method for method in result.related_methods}
    return [
        (call.receiver, call.resolution,
         sorted(methods[target].qualified_name for target in call.target_ids))
        for call in result.cross_file_calls
    ]


FIELD = source("Field", "class Field {\n    void ping() {}\n}")
LOCAL = source("Local", "class Local {\n    void ping() {}\n    boolean active() { return true; }\n    void step() {}\n}")


@pytest.mark.parametrize("header", [
    "for (Local value = new Local(); value.active(); value.step())",
    "for (var value = new Local(); value.active(); value.step())",
    "for (final example.Local<String> value = new Local<>(); active; step())",
    "try (Local value = new Local())",
    "try (var value = new Local(); var other = new Local();)",
])
def test_loop_and_resource_scopes_restore_fields_and_keep_nested_locals(header: str) -> None:
    result = analyze(
        "class Consumer {\n    Field value;\n    void run() {\n"
        f"        {header} {{\n"
        "            value.ping();\n            this.value.ping();\n"
        "            if (ready()) {\n                var helper = new Local();\n"
        "                helper.ping();\n            }\n        }\n"
        "        value.ping();\n        helper.ping();\n    }\n}\n",
        FIELD, LOCAL,
    )
    assert targets(result) == [
        ("value", "resolved", ["example.Local.ping"]),
        ("this.value", "resolved", ["example.Field.ping"]),
        ("helper", "resolved", ["example.Local.ping"]),
        ("value", "resolved", ["example.Field.ping"]),
    ]


@pytest.mark.parametrize("header", [
    "for (;;)", "for (index = 0; index < 2; index++)", "try (value)",
])
def test_headers_without_new_bindings_keep_outer_receivers(header: str) -> None:
    result = analyze(
        "class Consumer {\n    Field value;\n    void run() {\n"
        f"        {header} {{\n            value.ping();\n        }}\n    }}\n}}\n",
        FIELD,
    )
    assert targets(result) == [("value", "resolved", ["example.Field.ping"])]


@pytest.mark.parametrize("header", [
    "for (var value = Factory.create(); active; step())",
    "try (var value = Factory.create())",
])
def test_unknown_header_binding_does_not_fall_back_to_field(header: str) -> None:
    result = analyze(
        "class Consumer {\n    Field value;\n    void run() {\n"
        f"        {header} {{\n            value.ping();\n"
        "            this.value.ping();\n        }\n        value.ping();\n    }\n}\n",
        FIELD,
    )
    assert targets(result) == [
        ("this.value", "resolved", ["example.Field.ping"]),
        ("value", "resolved", ["example.Field.ping"]),
    ]


@pytest.mark.parametrize("arguments, expected_count", [
    ("", 1), ("/* empty */", 1), ('""', 2), ("'x'", 2),
    ('"comma, and )"', 2), ('"""text, ) {}"""', 2),
    ("factory(1, 2), 3", 1),
    ("new Box<A, B>()", 4),  # Unknown expression grammar: no narrowing.
])
def test_arity_counts_literals_comments_and_nested_calls_conservatively(
    arguments: str, expected_count: int,
) -> None:
    service = source("Service", "class Service {\n"
                     "    void ping() {}\n    void ping(String value) {}\n"
                     "    void ping(int value) {}\n    void ping(int left, int right) {}\n}")
    result = analyze(
        "class Consumer {\n    void run(Service service) {\n"
        f"        service.ping({arguments});\n    }}\n}}\n", service,
    )
    assert len(result.cross_file_calls) == 1
    call = result.cross_file_calls[0]
    assert len(call.target_ids) == expected_count
    assert call.resolution == ("resolved" if expected_count == 1 else "ambiguous")


@pytest.mark.parametrize("arguments", ["", '"one"', '"one", "two"'])
def test_varargs_accept_zero_or_more_values(arguments: str) -> None:
    service = source("Service", "class Service {\n    void ping(String... values) {}\n}")
    result = analyze(
        "class Consumer {\n    void run(Service service) {\n"
        f"        service.ping({arguments});\n    }}\n}}\n", service,
    )
    assert targets(result) == [("service", "resolved", ["example.Service.ping"])]


def test_same_file_calls_use_the_same_arity_and_scope_rules() -> None:
    result = analyze(
        "class Consumer {\n    void ping() {}\n    void ping(String value) {}\n"
        "    void run() {\n        ping();\n        this.ping(\"\");\n"
        "        Runnable action = () -> { ping(); };\n    }\n}\n",
    )
    assert [(call.line, call.resolution, len(call.callee_ids)) for call in result.calls] == [
        (6, "resolved", 1), (7, "resolved", 1),
    ]


def test_inherited_methods_and_overloads_keep_signature_based_overrides() -> None:
    base = source("Base", "class Base {\n    public void ping(int value) {}\n"
                  "    public void ping(String value) {}\n    private void hidden() {}\n}")
    child = source("Child", "class Child extends Base {\n    public void ping(int value) {}\n}")
    result = analyze(
        "class Consumer {\n    void run(Child child) {\n"
        "        child.ping(value);\n        child.hidden();\n    }\n}\n", base, child,
    )
    assert targets(result) == [
        ("child", "ambiguous", ["example.Base.ping", "example.Child.ping"]),
    ]
    assert len(result.cross_file_calls[0].target_ids) == 2


def test_this_super_and_unqualified_inherited_calls_link_to_original_symbols() -> None:
    base = source("Base", "class Base {\n    public void ping() {}\n    private void hidden() {}\n}")
    result = analyze(
        "class Consumer extends Base {\n    void run() {\n"
        "        ping();\n        this.ping();\n        super.ping();\n"
        "        super.hidden();\n    }\n}\n", base,
    )
    assert targets(result) == [
        ("this", "resolved", ["example.Base.ping"]),
        ("this", "resolved", ["example.Base.ping"]),
        ("super", "resolved", ["example.Base.ping"]),
    ]
    base_view = analyze_java(base.content, source_id=base.source_id)
    ping = next(symbol for symbol in base_view.symbols if symbol.kind == "method" and symbol.name == "ping")
    assert all(call.target_ids == [ping.id] for call in result.cross_file_calls)


def test_current_source_override_does_not_link_to_hidden_parent() -> None:
    base = source("Base", "class Base {\n    public void ping() {}\n}")
    result = analyze(
        "class Consumer extends Base {\n    public void ping() {}\n    void run() {\n"
        "        this.ping();\n        super.ping();\n    }\n}\n", base,
    )
    assert targets(result) == [("super", "resolved", ["example.Base.ping"])]
    assert len(result.calls) == 1


def test_this_identity_does_not_mix_other_versions_of_the_current_type() -> None:
    previous = source("Consumer", "class Consumer {\n    void own() {}\n}")
    result = analyze(
        "class Consumer {\n    void own() {}\n    void run() {\n"
        "        this.own();\n    }\n}\n", previous,
    )
    assert result.cross_file_calls == []
    assert len(result.calls) == 1


def test_super_keeps_the_callers_package_visibility_context() -> None:
    base = source("Base", "public class Base {\n    void hidden() {}\n"
                  "    public void ping() {}\n}", "api")
    result = analyze(
        "import api.Base;\nclass Consumer extends Base {\n    void run() {\n"
        "        super.hidden();\n        super.ping();\n    }\n}\n", base,
    )
    assert targets(result) == [("super", "resolved", ["api.Base.ping"])]


def test_inherited_imports_interfaces_and_diamond_targets_are_deduplicated() -> None:
    port = source("Port", "public interface Port {\n    void ping();\n}", "api")
    left = source("Left", "import api.Port;\ninterface Left extends Port {}")
    right = source("Right", "import api.Port;\ninterface Right extends Port {}")
    child = source("Child", "class Child implements Left, Right {}")
    result = analyze(
        "class Consumer {\n    void run(Child child) {\n        child.ping();\n    }\n}\n",
        port, left, right, child,
    )
    assert targets(result) == [("child", "resolved", ["api.Port.ping"])]


def test_package_private_methods_do_not_cross_package_inheritance() -> None:
    base = source("Base", "public class Base {\n    void hidden() {}\n    public void ping() {}\n}", "api")
    child = source("Child", "import api.Base;\nclass Child extends Base {}")
    result = analyze(
        "class Consumer {\n    void run(Child child) {\n"
        "        child.hidden();\n        child.ping();\n    }\n}\n", base, child,
    )
    assert targets(result) == [("child", "resolved", ["api.Base.ping"])]


def test_duplicate_parent_versions_remain_ambiguous() -> None:
    first = source("Base", "class Base {\n    public void ping() {}\n}")
    second = source("Base", "class Base {\n    public void ping() { updated(); }\n}")
    child = source("Child", "class Child extends Base {}")
    result = analyze(
        "class Consumer {\n    void run(Child child) {\n        child.ping();\n    }\n}\n",
        first, second, child,
    )
    assert targets(result) == [("child", "ambiguous", ["example.Base.ping", "example.Base.ping"])]


def test_inheritance_cycles_and_visit_limit_report_truncation(monkeypatch) -> None:
    first = source("First", "class First extends Second {}")
    second = source("Second", "class Second extends First {}")
    body = "class Consumer {\n    void run(First item) {\n        item.ping();\n    }\n}\n"
    result = analyze(body, first, second)
    assert result.cross_file_calls == []
    assert result.truncated is True
    monkeypatch.setattr(java_source, "MAX_INHERITANCE_VISITS", 1)
    second = source("Second", "class Second {\n    public void ping() {}\n}")
    result = analyze(body, first, second)
    assert result.cross_file_calls == []
    assert result.truncated is True


def test_api_acceptance_combines_resource_loop_inheritance_and_arity(client: TestClient) -> None:
    project = create_project(client)
    parent = upload_java(
        client, project, name="Base.java", relative_path="src/example/Base.java",
        content="package example;\nclass Base {\n    public void ping() {}\n    public void ping(int value) {}\n}\n",
    )
    upload_java(
        client, project, name="Resource.java", relative_path="src/example/Resource.java",
        content="package example;\nclass Resource extends Base {}\n",
    )
    consumer = upload_java(
        client, project, name="Consumer.java", relative_path="src/example/Consumer.java",
        content=("package example;\nclass Consumer {\n    void run() {\n"
                 "        try (var resource = new Resource()) {\n"
                 "            for (int i = 0; i < 2; i++) {\n"
                 "                resource.ping();\n            }\n        }\n"
                 "        resource.ping();\n    }\n}\n"),
    )
    url = f"/api/v1/sources/{consumer['source_id']}/code-structure"
    response = client.get(url)
    assert response.status_code == 200
    result = response.json()
    assert len(result["cross_file_calls"]) == 1
    call = result["cross_file_calls"][0]
    assert (call["line"], call["resolution"]) == (6, "resolved")
    assert result["related_methods"][0]["source_id"] == parent["source_id"]
    assert result["related_methods"][0]["start_line"] == 3
    assert client.get(url).json() == result
