"""Factory receivers preserve source identities, scope, and conservative lookup."""

import pytest
from fastapi.testclient import TestClient

from app.services import java_source
from app.services.java_source import analyze_java
from tests.test_java_structure import upload_java
from tests.test_java_v1 import analyze, source, targets
from tests.test_sources import create_project


PRODUCT = source("Product", "public class Product {\n    public void ping() {}\n}", "model")
OTHER = source("Other", "public class Other {\n    public void ping() {}\n}", "model")
FACTORY = source(
    "Factory", "import model.Product;\npublic class Factory {\n"
    "    public static Product create() { return null; }\n}", "tools",
)


def product_calls(result):
    return [item for item in targets(result) if item[0] == "product"]


@pytest.mark.parametrize("import_name", ["tools.Factory.create", "tools.Factory.*"])
def test_imported_factory_var_preserves_original_method_and_line(import_name: str) -> None:
    body = (
        f"import static {import_name};\nclass Consumer {{\n    void run() {{\n"
        "        var product = create(/* argument-free */);\n"
        "        product.ping();\n    }\n}\n"
    )
    result = analyze(body, FACTORY, PRODUCT)
    assert targets(result) == [
        ("import static", "resolved", ["tools.Factory.create"]),
        ("product", "resolved", ["model.Product.ping"]),
    ]
    assert result.cross_file_calls[1].line == 6
    original = analyze_java(PRODUCT.content, source_id=PRODUCT.source_id)
    method = next(item for item in original.symbols if item.name == "ping")
    assert result.cross_file_calls[1].target_ids == [method.id]
    assert analyze(body, FACTORY, PRODUCT) == result


def test_explicit_factory_import_precedes_wildcard_return_type() -> None:
    alternate = source(
        "Alternate", "public class Alternate {\n"
        "    public static model.Other create() { return null; }\n}", "tools",
    )
    result = analyze(
        "import static tools.Factory.create;\nimport static tools.Alternate.*;\n"
        "class Consumer {\n    void run() {\n        var product = create();\n"
        "        product.ping();\n    }\n}\n", FACTORY, alternate, PRODUCT, OTHER,
    )
    assert product_calls(result) == [("product", "resolved", ["model.Product.ping"])]


def test_imported_factory_selects_return_candidates_by_arity_and_varargs() -> None:
    factory = source(
        "Factory", "public class Factory {\n"
        "    public static model.Product create() { return null; }\n"
        "    public static model.Other create(String first, String... rest) { return null; }\n"
        "}", "tools",
    )
    result = analyze(
        "import static tools.Factory.*;\nclass Consumer {\n    void run() {\n"
        '        var product = create("one", "two");\n'
        "        product.ping();\n    }\n}\n", factory, PRODUCT, OTHER,
    )
    assert product_calls(result) == [("product", "resolved", ["model.Other.ping"])]
    assert result.cross_file_calls[0].resolution == "resolved"


@pytest.mark.parametrize("imports", [
    "import static missing.Factory.create;\nimport static tools.Factory.*;",
    "import static tools.Factory.create;\nimport static missing.Factory.create;",
    "import static tools.Factory.*;\nimport static missing.Factory.*;",
])
def test_missing_import_owner_keeps_factory_result_unknown(imports: str) -> None:
    result = analyze(
        f"{imports}\nclass Consumer {{\n    void run() {{\n"
        "        var product = create();\n        product.ping();\n    }\n}\n",
        FACTORY, PRODUCT,
    )
    assert product_calls(result) == []


@pytest.mark.parametrize("alternate_return, expected", [
    ("model.Product", [("product", "resolved", ["model.Product.ping"])]),
    ("model.Other", []),
    ("external.Missing", []),
    ("model.Product[]", []),
])
def test_factory_overloads_require_agreement_on_return_type(
    alternate_return: str, expected: list,
) -> None:
    overloads = source(
        "Factory", "public class Factory {\n"
        "    public static model.Product create(int value) { return null; }\n"
        f"    public static {alternate_return} create(String value) {{ return null; }}\n"
        "}", "tools",
    )
    result = analyze(
        "import static tools.Factory.*;\nclass Consumer {\n    void run() {\n"
        "        var product = create(1);\n        product.ping();\n    }\n}\n",
        overloads, PRODUCT, OTHER,
    )
    assert product_calls(result) == expected
    assert result.cross_file_calls[0].resolution == "ambiguous"


@pytest.mark.parametrize("member", [
    "static model.Other create(int value) { return null; }",
    "model.Other create() { return null; }",
    "static external.Missing create() { return null; }",
])
def test_member_name_blocks_import_even_if_it_cannot_infer_receiver(member: str) -> None:
    result = analyze(
        "import static tools.Factory.*;\nclass Consumer {\n"
        f"    {member}\n    void run() {{\n"
        "        var product = create();\n        product.ping();\n    }\n}\n",
        FACTORY, PRODUCT, OTHER,
    )
    assert product_calls(result) == []
    assert all(call.receiver != "import static" for call in result.cross_file_calls)


def test_private_current_static_factory_precedes_import() -> None:
    result = analyze(
        "import static tools.Factory.*;\nclass Consumer {\n"
        "    private static model.Other create() { return null; }\n"
        "    void run() {\n        var product = create();\n"
        "        product.ping();\n    }\n}\n", FACTORY, PRODUCT, OTHER,
    )
    assert targets(result) == [("product", "resolved", ["model.Other.ping"])]
    assert len(result.calls) == 1


@pytest.mark.parametrize("initializer", ["create(unknown)", "Consumer.create(unknown)"])
def test_mixed_instance_and_static_overloads_do_not_guess_static_factory(initializer: str) -> None:
    result = analyze(
        "class Consumer {\n"
        "    static model.Product create(int value) { return null; }\n"
        "    model.Other create(String value) { return null; }\n"
        f"    void run() {{\n        var product = {initializer};\n"
        "        product.ping();\n    }\n}\n", PRODUCT, OTHER,
    )
    assert product_calls(result) == []


def test_inherited_static_factory_retains_original_declaration_and_varargs() -> None:
    base = source(
        "Base", "class Base {\n"
        "    static model.Product create(String... values) { return null; }\n}",
    )
    result = analyze(
        "class Consumer extends Base {\n    void run() {\n"
        '        var product = create("one", "two");\n'
        "        product.ping();\n    }\n}\n", base, PRODUCT,
    )
    assert targets(result) == [
        ("this", "resolved", ["example.Base.create"]),
        ("product", "resolved", ["model.Product.ping"]),
    ]


def test_factory_binding_exits_lexical_block_and_restores_field() -> None:
    result = analyze(
        "import static tools.Factory.*;\nclass Consumer {\n"
        "    model.Other product;\n    void run() {\n"
        "        if (ready()) {\n            var product = create();\n"
        "            product.ping();\n        }\n        product.ping();\n    }\n}\n",
        FACTORY, PRODUCT, OTHER,
    )
    assert product_calls(result) == [
        ("product", "resolved", ["model.Product.ping"]),
        ("product", "resolved", ["model.Other.ping"]),
    ]


def test_duplicate_product_versions_remain_ambiguous() -> None:
    updated = source("Product", "public class Product {\n    public void ping() { changed(); }\n}", "model")
    result = analyze(
        "import static tools.Factory.*;\nclass Consumer {\n    void run() {\n"
        "        var product = create();\n        product.ping();\n    }\n}\n",
        FACTORY, PRODUCT, updated,
    )
    assert product_calls(result) == [
        ("product", "ambiguous", ["model.Product.ping", "model.Product.ping"]),
    ]


@pytest.mark.parametrize("initializer", [
    "create().copy()", "(create())", "flag ? create() : create()",
    "this.create()", "new Object() { Object get() { return create(); } }",
])
def test_unsupported_factory_expressions_keep_local_unknown(initializer: str) -> None:
    result = analyze(
        "import static tools.Factory.*;\nclass Consumer {\n    void run() {\n"
        f"        var product = {initializer};\n"
        "        product.ping();\n    }\n}\n", FACTORY, PRODUCT,
    )
    assert product_calls(result) == []


@pytest.mark.parametrize("prefix, parameter, local", [
    ("", "Object Factory", ""),
    ("    Object Factory;\n", "", ""),
    ("", "", "        var Factory = external();\n"),
    ("", "", "        Object Factory = external();\n"),
])
def test_qualified_factory_name_shadowing_does_not_infer_type(
    prefix: str, parameter: str, local: str,
) -> None:
    result = analyze(
        "import tools.Factory;\nclass Consumer {\n"
        f"{prefix}    void run({parameter}) {{\n{local}"
        "        var product = Factory.create();\n"
        "        product.ping();\n    }\n}\n", FACTORY, PRODUCT,
    )
    assert product_calls(result) == []


def test_generic_factory_type_parameter_does_not_resolve_to_same_named_class() -> None:
    generic = source(
        "Factory", "public class Factory {\n"
        "    public static <Product> Product create() { return null; }\n}", "tools",
    )
    collision = source("Product", "public class Product {\n    public void ping() {}\n}", "tools")
    result = analyze(
        "import static tools.Factory.*;\nclass Consumer {\n    void run() {\n"
        "        var product = create();\n        product.ping();\n    }\n}\n",
        generic, collision,
    )
    assert product_calls(result) == []


def test_incomplete_member_lookup_suppresses_factory_import_inference() -> None:
    base = source("Base", "class Base extends Base {}")
    result = analyze(
        "import static tools.Factory.*;\nclass Consumer extends Base {\n    void run() {\n"
        "        var product = create();\n        product.ping();\n    }\n}\n",
        base, FACTORY, PRODUCT,
    )
    assert result.truncated
    assert product_calls(result) == []


def test_factory_results_obey_output_budgets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(java_source, "MAX_RELATED_METHODS", 1)
    result = analyze(
        "import static tools.Factory.*;\nclass Consumer {\n    void run() {\n"
        "        var product = create();\n        product.ping();\n    }\n}\n",
        FACTORY, PRODUCT,
    )
    assert result.truncated
    visible = {method.id for method in result.related_methods}
    assert all(set(call.target_ids) <= visible for call in result.cross_file_calls)


def test_api_factory_inference_requires_ready_sources_in_same_repository(client: TestClient) -> None:
    project = create_project(client)
    other_project = create_project(client)
    repositories = [client.post(
        f"/api/v1/projects/{project}/repositories/resolve", json={"name": name},
    ).json()["id"] for name in ("app", "unrelated")]
    for project_id, repository_id in [(other_project, None), (project, repositories[1])]:
        upload_java(
            client, project_id, name="Factory.java", relative_path=FACTORY.source_path,
            content=FACTORY.content, repository_id=repository_id,
        )
    factory = upload_java(
        client, project, name="Factory.java", relative_path=FACTORY.source_path,
        content=FACTORY.content, repository_id=repositories[0], parse=False,
    )
    product = upload_java(
        client, project, name="Product.java", relative_path=PRODUCT.source_path,
        content=PRODUCT.content, repository_id=repositories[0],
    )
    consumer = upload_java(
        client, project, name="Consumer.java", relative_path="src/example/Consumer.java",
        repository_id=repositories[0], content="package example;\nimport static tools.Factory.*;\n"
        "class Consumer {\n    void run() {\n        var product = create();\n"
        "        product.ping();\n    }\n}\n",
    )
    endpoint = f"/api/v1/sources/{consumer['source_id']}/code-structure"
    assert client.get(endpoint).json()["cross_file_calls"] == []
    assert client.post(f"/api/v1/tasks/{factory['task_id']}/run").json()["status"] == "succeeded"
    response = client.get(endpoint)
    assert response.status_code == 200
    result = response.json()
    assert [(call["receiver"], call["line"]) for call in result["cross_file_calls"]] == [
        ("import static", 5), ("product", 6),
    ]
    assert {method["source_id"] for method in result["related_methods"]} == {
        factory["source_id"], product["source_id"],
    }
    assert client.get(endpoint).json() == result
