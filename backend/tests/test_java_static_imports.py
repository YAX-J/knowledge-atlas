"""Repository-local static imports retain conservative candidate boundaries."""

import pytest
from fastapi.testclient import TestClient

from app.services import java_source
from app.services.java_source import analyze_java
from tests.test_java_structure import upload_java
from tests.test_java_v1 import analyze, source, targets
from tests.test_sources import create_project


TOOLS = source("Tools", "public class Tools {\n    public static void ping() {}\n}", "tools")


@pytest.mark.parametrize("import_name", ["tools.Tools.ping", "tools.Tools.*"])
def test_static_import_links_original_symbol_and_exact_lines(import_name: str) -> None:
    body = f"import static {import_name};\nclass Consumer {{\n    void run() {{\n        ping();\n    }}\n}}\n"
    result = analyze(body, TOOLS)
    assert targets(result) == [("import static", "resolved", ["tools.Tools.ping"])]
    assert result.cross_file_calls[0].line == 5
    original = analyze_java(TOOLS.content, source_id=TOOLS.source_id)
    method = next(item for item in original.symbols if item.kind == "method")
    assert result.cross_file_calls[0].target_ids == [method.id]
    assert result.related_methods[0].start_line == 3
    assert analyze(body, TOOLS) == result


def test_explicit_import_precedes_wildcard_and_duplicates_are_deduplicated() -> None:
    other = source("Other", "public class Other {\n    public static void ping() {}\n}", "tools")
    result = analyze(
        "import static tools.Tools.ping;\nimport static tools.Tools.ping;\n"
        "import static tools.Other.*;\nclass Consumer {\n    void run() {\n        ping();\n    }\n}\n",
        TOOLS, other,
    )
    assert targets(result) == [("import static", "resolved", ["tools.Tools.ping"])]


@pytest.mark.parametrize("imports", [
    "import static tools.Tools.*;\nimport static tools.Other.*;",
    "import static tools.Tools.ping;\nimport static tools.Other.ping;",
])
def test_colliding_imports_remain_ambiguous(imports: str) -> None:
    other = source("Other", "public class Other {\n    public static void ping() {}\n}", "tools")
    result = analyze(f"{imports}\nclass Consumer {{\n    void run() {{\n        ping();\n    }}\n}}\n", TOOLS, other)
    assert targets(result) == [("import static", "ambiguous", ["tools.Other.ping", "tools.Tools.ping"])]


def test_static_overloads_reuse_arity_and_varargs_filtering() -> None:
    tools = source("Tools", "public class Tools {\n    public static void ping() {}\n"
                   "    public static void ping(String value) {}\n"
                   "    public static void ping(int value) {}\n"
                   "    public static void ping(String first, String... rest) {}\n}", "tools")
    result = analyze(
        "import static tools.Tools.*;\nclass Consumer {\n    void run() {\n"
        "        ping();\n        ping(1);\n        ping(1, 2);\n    }\n}\n", tools,
    )
    assert [(call.resolution, len(call.target_ids)) for call in result.cross_file_calls] == [
        ("resolved", 1), ("ambiguous", 3), ("resolved", 1),
    ]


@pytest.mark.parametrize("member", ["void ping() {}", "void ping(int value) {}"])
def test_current_member_name_blocks_import_fallback_even_with_wrong_arity(member: str) -> None:
    result = analyze(
        f"import static tools.Tools.ping;\nclass Consumer {{\n    {member}\n"
        "    void run() {\n        ping();\n    }\n}\n", TOOLS,
    )
    assert result.cross_file_calls == []


def test_inherited_member_precedes_import_and_this_never_uses_import() -> None:
    base = source("Base", "class Base {\n    public void ping() {}\n}")
    result = analyze(
        "import static tools.Tools.*;\nclass Consumer extends Base {\n    void run() {\n"
        "        ping();\n        this.ping();\n    }\n}\n", base, TOOLS,
    )
    assert targets(result) == [("this", "resolved", ["example.Base.ping"])] * 2
    result = analyze(
        "import static tools.Tools.*;\nclass Consumer {\n    void run() {\n"
        "        this.ping();\n        super.ping();\n    }\n}\n", TOOLS,
    )
    assert result.cross_file_calls == []


@pytest.mark.parametrize("member", [
    "public void ping() {}", "private static void ping() {}",
    "protected static void ping() {}", "static void ping() {}",
])
def test_nonstatic_private_or_inaccessible_members_are_not_imported(member: str) -> None:
    tools = source("Tools", f"public class Tools {{\n    {member}\n}}", "tools")
    result = analyze(
        "import static tools.Tools.*;\nclass Consumer {\n    void run() {\n        ping();\n    }\n}\n", tools,
    )
    assert result.cross_file_calls == []


def test_nonpublic_import_owner_is_not_accessible_across_packages() -> None:
    tools = source("Tools", "class Tools {\n    public static void ping() {}\n}", "tools")
    assert analyze(
        "import static tools.Tools.*;\nclass Consumer {\n    void run() {\n        ping();\n    }\n}\n", tools,
    ).cross_file_calls == []


def test_same_package_static_and_implicit_public_interface_methods() -> None:
    tools = source("Tools", "class Tools {\n    static void ping() {}\n}")
    port = source("Port", "public interface Port {\n    static void pong() {}\n}", "tools")
    result = analyze(
        "import static example.Tools.ping;\nimport static tools.Port.*;\nclass Consumer {\n"
        "    void run() {\n        ping();\n        pong();\n    }\n}\n", tools, port,
    )
    assert targets(result) == [
        ("import static", "resolved", ["example.Tools.ping"]),
        ("import static", "resolved", ["tools.Port.pong"]),
    ]


def test_imports_can_follow_inherited_class_statics_but_not_interface_statics() -> None:
    base = source("Base", "public class Base {\n    public static void ping() {}\n}", "tools")
    child = source("Child", "public class Child extends Base {}", "tools")
    port = source("Port", "public interface Port {\n    static void pong() {}\n}", "tools")
    impl = source("Impl", "public class Impl implements Port {}", "tools")
    result = analyze(
        "import static tools.Child.*;\nimport static tools.Impl.*;\nclass Consumer {\n"
        "    void run() {\n        ping();\n        pong();\n    }\n}\n", base, child, port, impl,
    )
    assert targets(result) == [("import static", "resolved", ["tools.Base.ping"])]


def test_missing_explicit_owner_blocks_wildcard_and_unimported_names_are_ignored() -> None:
    result = analyze(
        "import static absent.Tools.ping;\nimport static tools.Tools.*;\nclass Consumer {\n"
        "    void run() {\n        ping();\n    }\n}\n", TOOLS,
    )
    assert result.cross_file_calls == []
    assert analyze("class Consumer {\n    void run() {\n        ping();\n    }\n}\n", TOOLS).cross_file_calls == []


def test_duplicate_versions_are_ambiguous_and_unsupported_scopes_are_omitted() -> None:
    updated = source("Tools", "public class Tools {\n    public static void ping() { updated(); }\n}", "tools")
    result = analyze(
        "import static tools.Tools.*;\nclass Consumer {\n    void run() {\n"
        "        ping();\n        Runnable action = () -> { ping(); };\n    }\n}\n", TOOLS, updated,
    )
    assert targets(result) == [("import static", "ambiguous", ["tools.Tools.ping"] * 2)]


def test_import_output_limits_do_not_leave_dangling_edges(monkeypatch) -> None:
    monkeypatch.setattr(java_source, "MAX_RELATED_METHODS", 1)
    other = source("Other", "public class Other {\n    public static void ping() {}\n}", "tools")
    result = analyze(
        "import static tools.Tools.*;\nimport static tools.Other.*;\nclass Consumer {\n"
        "    void run() {\n        ping();\n    }\n}\n", TOOLS, other,
    )
    assert result.truncated
    assert result.cross_file_calls == []
    assert result.related_methods == []


def test_incomplete_member_lookup_does_not_guess_static_import_fallback() -> None:
    base = source("Base", "class Base extends Base {}")
    result = analyze(
        "import static tools.Tools.*;\nclass Consumer extends Base {\n    void run() {\n"
        "        ping();\n    }\n}\n", base, TOOLS,
    )
    assert result.truncated
    assert result.cross_file_calls == []


def test_api_static_imports_keep_readiness_repository_and_project_boundaries(client: TestClient) -> None:
    project = create_project(client)
    other_project = create_project(client)
    repositories = [client.post(
        f"/api/v1/projects/{project}/repositories/resolve", json={"name": name},
    ).json()["id"] for name in ("app", "unrelated")]
    content = "package tools;\npublic class Tools {\n    public static void ping() {}\n}\n"
    for project_id, repository_id, parse in [
        (project, repositories[1], True), (other_project, None, True),
        (project, repositories[0], False),
    ]:
        pending = upload_java(client, project_id, name="Tools.java", relative_path="src/tools/Tools.java",
                              content=content, repository_id=repository_id, parse=parse)
    consumer = upload_java(
        client, project, name="Consumer.java", relative_path="src/example/Consumer.java",
        repository_id=repositories[0], content="package example;\nimport static tools.Tools.ping;\n"
        "class Consumer {\n    void run() {\n        ping();\n    }\n}\n",
    )
    url = f"/api/v1/sources/{consumer['source_id']}/code-structure"
    assert client.get(url).json()["cross_file_calls"] == []
    assert client.post(f"/api/v1/tasks/{pending['task_id']}/run").json()["status"] == "succeeded"
    result = client.get(url).json()
    assert len(result["cross_file_calls"]) == 1
    assert result["cross_file_calls"][0]["receiver"] == "import static"
    assert result["cross_file_calls"][0]["line"] == 5
    assert result["related_methods"][0]["source_id"] == pending["source_id"]
    assert client.get(url).json() == result
