import uuid

import pytest
from pydantic import SecretStr

from app.api.routes import sources as source_routes
from app.core.config import Settings
from app.schemas.code_agent import AgentCallAnalysisDraft
from app.services import deepseek
from tests.test_sources import create_project


@pytest.fixture
def configured(monkeypatch):
    settings = Settings(_env_file=None, deepseek_api_key=SecretStr("test-secret-key"))
    monkeypatch.setattr(source_routes, "get_settings", lambda: settings)
    return settings


def _repository(client, project_id: str) -> str:
    response = client.post(
        f"/api/v1/projects/{project_id}/repositories/resolve",
        json={"name": "agent-fixture", "kind": "local_folder"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _code(client, project_id: str, repository_id: str, path: str, content: str) -> dict:
    response = client.post(
        f"/api/v1/projects/{project_id}/sources",
        data={"repository_id": repository_id, "relative_path": path},
        files={"file": (path.rsplit("/", 1)[-1], content.encode())},
    )
    assert response.status_code == 202, response.text
    uploaded = response.json()
    task = client.post(f"/api/v1/tasks/{uploaded['task_id']}/run")
    assert task.status_code == 200 and task.json()["status"] == "succeeded", task.text
    return uploaded


LANGUAGE_CASES = [
    ("service.py", "def save(value):\n    return value\n", "main.py", "from service import save\ndef run():\n    return save('x')\n", "save"),
    ("service.ts", "export function save(value: string) { return value }\n", "main.js", "import { save } from './service'\nexport function run() { return save('x') }\n", "save"),
    ("service.go", "package demo\nfunc Save(value string) string { return value }\n", "main.go", "package demo\nfunc Run() string { return Save(\"x\") }\n", "Save"),
    ("service.c", "int save(void) { return 1; }\n", "main.cpp", "int save(void);\nint run(void) { return save(); }\n", "save"),
    ("Service.cs", "namespace Demo { class Service { public void Save() {} } }\n", "Main.cs", "namespace Demo { class Main { void Run() { new Service().Save(); } } }\n", "Save"),
    ("Validator.java", "package demo;\nclass Validator {\n static void save() {}\n}\n", "Main.java", "package demo;\nclass Main {\n void run() { Validator.save(); }\n}\n", "save"),
]


@pytest.mark.parametrize("target_path,target_content,caller_path,caller_content,callee", LANGUAGE_CASES)
def test_agent_resolves_bounded_multilanguage_candidates_with_server_evidence(
    client, configured, monkeypatch,
    target_path, target_content, caller_path, caller_content, callee,
):
    project_id = create_project(client)
    repository_id = _repository(client, project_id)
    target = _code(client, project_id, repository_id, f"src/{target_path}", target_content)
    caller = _code(client, project_id, repository_id, f"src/{caller_path}", caller_content)
    payloads = []

    def analyze(_settings, payload):
        payloads.append(payload)
        assert len(payload["calls"]) == 1
        call = payload["calls"][0]
        assert call["callee_name"] == callee
        assert len(call["candidates"]) == 1
        return AgentCallAnalysisDraft.model_validate({"decisions": [{
            "call_id": call["id"],
            "target_ids": [call["candidates"][0]["id"]],
            "resolution": "resolved",
            "confidence": 0.92,
            "resolution_basis": "导入、接收者与同名声明一致",
        }]})

    monkeypatch.setattr(deepseek, "analyze_cross_file_calls", analyze)
    response = client.post(f"/api/v1/sources/{caller['source_id']}/agent-call-analysis")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["provider_call_count"] == 1
    assert result["candidate_call_count"] == 1
    assert result["calls"][0]["callee_name"] == callee
    assert result["calls"][0]["resolution"] == "resolved"
    assert callee in result["calls"][0]["call_quote"]
    assert result["related_symbols"][0]["source_id"] == target["source_id"]
    assert result["related_symbols"][0]["quote"] in target_content
    assert len(payloads) == 1


def test_agent_rejects_target_outside_server_candidate_set(client, configured, monkeypatch):
    project_id = create_project(client)
    repository_id = _repository(client, project_id)
    _code(client, project_id, repository_id, "service.py", "def save():\n    return 1\n")
    caller = _code(client, project_id, repository_id, "main.py", "from service import save\nsave()\n")

    def forged(_settings, payload):
        return AgentCallAnalysisDraft.model_validate({"decisions": [{
            "call_id": payload["calls"][0]["id"],
            "target_ids": [str(uuid.uuid4())],
            "resolution": "resolved",
            "confidence": 1,
            "resolution_basis": "伪造目标",
        }]})

    monkeypatch.setattr(deepseek, "analyze_cross_file_calls", forged)
    response = client.post(f"/api/v1/sources/{caller['source_id']}/agent-call-analysis")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "CALL_AGENT_EVIDENCE_INVALID"
    assert "伪造目标" not in response.text


def test_no_cross_file_candidates_skips_provider_and_configuration(client, monkeypatch):
    project_id = create_project(client)
    source = _code(client, project_id, _repository(client, project_id), "main.py", "def run():\n    return print('x')\n")
    monkeypatch.setattr(
        deepseek,
        "analyze_cross_file_calls",
        lambda *_: pytest.fail("provider must not be called without repository-local candidates"),
    )
    response = client.post(f"/api/v1/sources/{source['source_id']}/agent-call-analysis")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["provider_call_count"] == 0
    assert result["calls"] == []
    assert result["model"] is None


def test_agent_requires_ready_code_and_configuration(client, configured):
    project_id = create_project(client)
    repository_id = _repository(client, project_id)
    pending = client.post(
        f"/api/v1/projects/{project_id}/sources",
        data={"repository_id": repository_id, "relative_path": "main.py"},
        files={"file": ("main.py", b"save()\n")},
    ).json()
    assert client.post(f"/api/v1/sources/{pending['source_id']}/agent-call-analysis").json()["error"]["code"] == "SOURCE_NOT_PARSED"

    _code(client, project_id, repository_id, "service.py", "def save():\n    return 1\n")
    client.post(f"/api/v1/tasks/{pending['task_id']}/run")
    configured.deepseek_api_key = None
    response = client.post(f"/api/v1/sources/{pending['source_id']}/agent-call-analysis")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "CALL_AGENT_NOT_CONFIGURED"
