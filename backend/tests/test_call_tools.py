import json
from pathlib import Path
import uuid

import httpx
from pydantic import SecretStr
import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.services import call_tools, code_agent, deepseek
from app.services.model_usage import begin_call, record_usage, usage_budget
from scripts.evaluate_calls import source_snapshot

ROOT = Path(__file__).resolve().parents[2] / "evaluation" / "calls"


def settings():
    return Settings(_env_file=None, deepseek_api_key=SecretStr("test-key"))


def snapshot():
    source, related = source_snapshot(ROOT, "python")
    calls, targets, *_ = code_agent._non_java_candidates(source, related)
    return source, related, calls, targets


def final_message(messages):
    payload = json.loads(messages[1]["content"])
    return {"content": json.dumps({"decisions": [{"call_id": call["id"], "target_ids": [],
                                                   "resolution": "unresolved", "confidence": .5,
                                                   "resolution_basis": "Insufficient type context"}
                                                  for call in payload["calls"]]})}


def tool_message(name, arguments, identifier="call-1"):
    return {"content": None, "tool_calls": [{"id": identifier, "type": "function",
                                             "function": {"name": name, "arguments": json.dumps(arguments)}}]}


def test_model_selects_read_tool_then_returns_validated_result(monkeypatch):
    source, related, _, _ = snapshot()
    rounds = []

    def turn(_settings, messages, tools, **kwargs):
        rounds.append(kwargs)
        if len(rounds) == 1:
            return tool_message("read_source_range", {"source_id": str(related[0].id), "start_line": 1, "end_line": 4})
        assert messages[-1]["role"] == "tool"
        assert "lines" in json.loads(messages[-1]["content"])
        return final_message(messages)

    monkeypatch.setattr(deepseek, "call_agent_turn", turn)
    result = code_agent.analyze_snapshot(source=source, related=related, settings=settings(), strategy="tools")
    assert result.provider_call_count == 2 and result.tool_call_count == 1
    assert result.tool_trace[0]["status"] == "ok"
    assert rounds[0]["require_tool"] is True
    assert all(call.resolution == "unresolved" for call in result.calls)


@pytest.mark.parametrize("name,args,error", [
    ("run_shell", {"cmd": "whoami"}, "TOOL_NOT_ALLOWED"),
    ("read_source_range", {"source_id": str(uuid.uuid4()), "start_line": 1, "end_line": 2}, "SOURCE_OUT_OF_SCOPE"),
    ("read_source_range", {"source_id": "../../secret", "start_line": 1, "end_line": 2}, "INVALID_ARGUMENTS"),
    ("search_symbols", {"query": "save", "sql": "delete from projects"}, "INVALID_ARGUMENTS"),
    ("find_references", {"symbol_id": str(uuid.uuid4())}, "SYMBOL_OUT_OF_SCOPE"),
])
def test_tool_scope_and_argument_fencing(name, args, error):
    source, related, _, targets = snapshot()
    result = call_tools.RepositoryTools([source, *related], targets).execute(name, json.dumps(args))
    assert result == {"error": error}


def test_read_range_budget_and_each_tool():
    source, related, _, targets = snapshot()
    tools = call_tools.RepositoryTools([source, *related], targets)
    key = next(iter(targets))
    assert tools.execute("read_source_range", json.dumps({"source_id": str(source.id), "start_line": 1, "end_line": 81}))["error"] == "LINE_RANGE_INVALID"
    assert tools.execute("get_imports", json.dumps({"source_id": str(source.id)}))["lines"]
    assert tools.execute("search_symbols", '{"query":"save"}')["symbols"]
    assert tools.execute("find_references", json.dumps({"symbol_id": str(key)}))["references"]
    assert tools.execute("get_type_members", json.dumps({"symbol_id": str(key)}))["symbols"]


def test_repeated_tool_loop_terminates_with_budget_error(monkeypatch):
    source, related, _, _ = snapshot()
    calls = 0

    def turn(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return tool_message("search_symbols", {"query": "save"}, f"call-{calls}")

    monkeypatch.setattr(deepseek, "call_agent_turn", turn)
    with pytest.raises(AppError) as error:
        code_agent.analyze_snapshot(source=source, related=related, settings=settings(), strategy="tools")
    assert error.value.code == "CALL_AGENT_BUDGET_EXCEEDED"
    assert calls == 4


def test_tool_final_decision_cannot_create_targets(monkeypatch):
    source, related, _, _ = snapshot()

    def turn(_settings, messages, *_args, **_kwargs):
        result = final_message(messages)
        content = json.loads(result["content"])
        content["decisions"][0].update(target_ids=[str(uuid.uuid4())], resolution="resolved")
        return {"content": json.dumps(content)}

    monkeypatch.setattr(deepseek, "call_agent_turn", turn)
    with pytest.raises(AppError) as error:
        code_agent.analyze_snapshot(source=source, related=related, settings=settings(), strategy="tools")
    assert error.value.code == "CALL_AGENT_EVIDENCE_INVALID"


def test_usage_meter_enforces_authorized_count_and_never_records_content():
    with usage_budget(1) as meter:
        begin_call("test")
        record_usage({"usage": {"prompt_tokens": 10, "completion_tokens": 2}, "secret": "not recorded"})
        with pytest.raises(RuntimeError):
            begin_call("overflow")
    assert meter.summary()["attempted"] == 1
    assert meter.summary()["prompt_tokens"] == 10
    assert "not recorded" not in json.dumps(meter.summary())


def test_tool_transport_uses_non_thinking_protocol_and_numeric_usage(monkeypatch):
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": '{"decisions": []}'}}],
                                         "usage": {"prompt_tokens": 8, "completion_tokens": 4}})

    original = httpx.Client
    monkeypatch.setattr(deepseek.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    with usage_budget(1) as meter:
        result = deepseek.call_agent_turn(settings(), [{"role": "user", "content": "public fixture"}], call_tools.TOOLS,
                                         finish=False, require_tool=True)
    assert result["content"] == '{"decisions": []}'
    assert captured[0]["tool_choice"] == "required"
    assert captured[0]["thinking"] == {"type": "disabled"}
    assert meter.summary()["completion_tokens"] == 4
