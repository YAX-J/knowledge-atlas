"""Regression coverage for receiver identity and unsupported array bindings."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.services.java_source import JavaSourceInput, analyze_java
from tests.test_java_structure import upload_java
from tests.test_java_v1 import analyze, source, targets
from tests.test_sources import create_project


PRODUCT = source("Product", "public class Product {\n    public void ping() {}\n}", "model")
OTHER = source("Other", "public class Other {\n    public void ping() {}\n}", "model")


@pytest.mark.parametrize("parameter", [
    "Product[] Product", "Product[][] Product", "Product Product[]",
    "Product Product[][]", "Product... Product", "final Product[] Product",
])
def test_array_parameter_shadows_field_and_type_without_element_calls(parameter: str) -> None:
    result = analyze(
        "import model.Product;\nclass Consumer {\n    model.Other Product;\n"
        f"    void run({parameter}) {{\n        Product.ping();\n"
        "        this.Product.ping();\n    }\n}\n", PRODUCT, OTHER,
    )
    assert targets(result) == [("this.Product", "resolved", ["model.Other.ping"])]


@pytest.mark.parametrize("declaration", [
    "Product[] Product", "Product[][] Product", "Product Product[]", "Product Product[][]",
])
def test_array_field_does_not_fall_back_to_imported_type(declaration: str) -> None:
    result = analyze(
        f"import model.Product;\nclass Consumer {{\n    {declaration};\n"
        "    void run() {\n        Product.ping();\n        this.Product.ping();\n    }\n}\n",
        PRODUCT,
    )
    assert result.cross_file_calls == []


@pytest.mark.parametrize("declaration", [
    "Product[] Product = null", "Product[][] Product = null",
    "Product Product[] = null", "Product Product[][] = null",
])
def test_array_local_shadows_only_its_block_and_restores_scalar_field(declaration: str) -> None:
    result = analyze(
        "import model.Product;\nclass Consumer {\n    model.Other Product;\n"
        "    void run() {\n        if (ready()) {\n"
        f"            {declaration};\n            Product.ping();\n"
        "            this.Product.ping();\n        }\n        Product.ping();\n    }\n}\n",
        PRODUCT, OTHER,
    )
    assert targets(result) == [
        ("this.Product", "resolved", ["model.Other.ping"]),
        ("Product", "resolved", ["model.Other.ping"]),
    ]


@pytest.mark.parametrize("binding_kind", ["field", "parameter", "local"])
def test_array_generic_argument_does_not_turn_scalar_receiver_into_array(binding_kind: str) -> None:
    field = "    Product<Other[]> product;\n" if binding_kind == "field" else ""
    parameter = "Product<Other[]> product" if binding_kind == "parameter" else ""
    local = "        Product<Other[]> product = null;\n" if binding_kind == "local" else ""
    result = analyze(
        "import model.Product;\nimport model.Other;\nclass Consumer {\n"
        f"{field}    void run({parameter}) {{\n{local}        product.ping();\n    }}\n}}\n",
        PRODUCT, OTHER,
    )
    assert targets(result) == [("product", "resolved", ["model.Product.ping"])]


@pytest.mark.parametrize("factory_call", ["Factory.create()", "create()"])
@pytest.mark.parametrize("duplicate_version", [False, True])
def test_factory_default_package_return_keeps_its_identity_across_caller_imports(
    factory_call: str, duplicate_version: bool,
) -> None:
    product_id = uuid.uuid4()
    factory = JavaSourceInput(
        uuid.uuid4(), "Factory.java",
        "class Factory {\n    static Product create() { return null; }\n}\n",
    )
    original_product = JavaSourceInput(
        product_id, "Product.java", "class Product {\n    void ping() {}\n}\n",
    )
    originals = [original_product]
    if duplicate_version:
        originals.append(JavaSourceInput(
            uuid.uuid4(), "Product.java", "class Product {\n    void ping() { changed(); }\n}\n",
        ))
    content = (
        "import model.Product;\nclass Consumer extends Factory {\n    void run() {\n"
        f"        var product = {factory_call};\n        product.ping();\n    }}\n}}\n"
    )
    result = analyze_java(
        content, source_id=uuid.uuid4(),
        related_sources=[factory, *originals, PRODUCT],
    )
    methods = {item.id: item for item in result.related_methods}
    call = next(item for item in result.cross_file_calls if item.receiver == "product")
    assert {methods[item].source_id for item in call.target_ids} == {
        item.source_id for item in originals
    }
    assert call.resolution == ("ambiguous" if duplicate_version else "resolved")
    assert call.line == 5


def test_constructor_var_still_resolves_in_caller_import_context() -> None:
    result = analyze(
        "import model.Product;\nclass Consumer {\n    void run() {\n"
        "        var product = new Product();\n        product.ping();\n    }\n}\n", PRODUCT,
    )
    assert targets(result) == [("product", "resolved", ["model.Product.ping"])]


def test_api_does_not_report_array_parameter_as_element_method(client: TestClient) -> None:
    project = create_project(client)
    product = upload_java(
        client, project, name="Product.java", relative_path=PRODUCT.source_path,
        content=PRODUCT.content,
    )
    consumer = upload_java(
        client, project, name="Consumer.java", relative_path="src/example/Consumer.java",
        content="package example;\nimport model.Product;\nclass Consumer {\n"
        "    void run(Product[] items, Product scalar) {\n"
        "        items.ping();\n        scalar.ping();\n    }\n}\n",
    )
    response = client.get(f"/api/v1/sources/{consumer['source_id']}/code-structure")
    assert response.status_code == 200
    result = response.json()
    assert [(item["receiver"], item["line"]) for item in result["cross_file_calls"]] == [
        ("scalar", 6),
    ]
    assert {item["source_id"] for item in result["related_methods"]} == {product["source_id"]}
