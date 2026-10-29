"""Bounded, evidence-validated Agent assistance for repository-local calls."""

import json
import uuid
from dataclasses import dataclass


from app.core.config import Settings
from app.core.errors import AppError
from app.agents.base import SourceFile as SourceDocument
from app.agents.runtime import invoke_model
from app.schemas.code_agent import (
    AgentCallAnalysisRead,
    AgentCrossFileCallRead,
    AgentRelatedSymbolRead,
)
from app.llm.providers import deepseek
from app.agents.code_analysis import graph as call_tools
from app.services.code_source import CodeCallSite, analyze_code
from app.services.java_source import JavaSourceInput, analyze_java, java_symbols
from app.services.source_languages import CODE_SOURCE_TYPES
from app.services import code_bindings, code_semantics


MAX_RELATED_SOURCES = 99
MAX_RELATED_BYTES = 20 * 1024 * 1024
MAX_AGENT_CALLS = 100
MAX_CANDIDATES_PER_CALL = 20
MAX_EXCERPT_CHARS = 20_000

LANGUAGE_FAMILIES = {
    "java": frozenset({"java"}),
    "python": frozenset({"python"}),
    "javascript": frozenset({"javascript", "jsx", "typescript", "tsx"}),
    "jsx": frozenset({"javascript", "jsx", "typescript", "tsx"}),
    "typescript": frozenset({"javascript", "jsx", "typescript", "tsx"}),
    "tsx": frozenset({"javascript", "jsx", "typescript", "tsx"}),
    "go": frozenset({"go"}),
    "c": frozenset({"c", "cpp"}),
    "cpp": frozenset({"c", "cpp"}),
    "csharp": frozenset({"csharp"}),
}


@dataclass(frozen=True)
class _Target:
    id: uuid.UUID
    source_id: uuid.UUID
    source_path: str
    language: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    quote: str


@dataclass(frozen=True)
class _Call:
    id: uuid.UUID
    caller_id: uuid.UUID | None
    receiver: str | None
    callee_name: str
    expression: str
    line: int
    column: int
    quote: str
    candidate_ids: tuple[uuid.UUID, ...]


def _line(content: str, number: int) -> str:
    lines = content.splitlines()
    return lines[number - 1] if 1 <= number <= len(lines) else ""


def _excerpt(content: str, call_lines: set[int]) -> str:
    lines = content.splitlines()
    selected = set(range(1, min(len(lines), 120) + 1))
    for line in call_lines:
        selected.update(range(max(1, line - 3), min(len(lines), line + 3) + 1))
    rendered = "\n".join(f"{line}: {lines[line - 1]}" for line in sorted(selected))
    return rendered[:MAX_EXCERPT_CHARS]


def _target(source: SourceDocument, symbol) -> _Target:
    return _Target(
        id=symbol.id,
        source_id=source.id,
        source_path=source.relative_path or source.original_name,
        language=source.source_type,
        name=symbol.name,
        qualified_name=symbol.qualified_name,
        start_line=symbol.start_line,
        end_line=symbol.end_line,
        quote=_line(source.content, symbol.start_line),
    )


def _non_java_candidates(
    source: SourceDocument, related: list[SourceDocument],
) -> tuple[list[_Call], dict[uuid.UUID, _Target], int, bool, bool]:
    current = analyze_code(source.content, source_id=source.id, language=source.source_type)
    targets: dict[uuid.UUID, _Target] = {}
    by_name: dict[str, list[_Target]] = {}
    truncated = current.truncated
    has_syntax_errors = current.has_syntax_errors
    for item in related:
        analysis = analyze_code(item.content, source_id=item.id, language=item.source_type)
        truncated |= analysis.truncated
        has_syntax_errors |= analysis.has_syntax_errors
        for symbol in analysis.symbols:
            if symbol.kind != "method":
                continue
            candidate = _target(item, symbol)
            targets[candidate.id] = candidate
            by_name.setdefault(candidate.name, []).append(candidate)
    calls: list[_Call] = []
    imports = code_bindings.bindings(source.content, source.source_type)
    for call in current.call_sites:
        imported = code_bindings.imported_candidates(source, call, targets, imports)
        candidates = sorted(imported if imported is not None else by_name.get(call.callee_name, []), key=lambda item: (
            item.source_path.casefold(), item.start_line, str(item.id),
        ))
        if not candidates:
            continue
        if len(candidates) > MAX_CANDIDATES_PER_CALL:
            candidates = candidates[:MAX_CANDIDATES_PER_CALL]
            truncated = True
        calls.append(_from_call_site(call, tuple(item.id for item in candidates)))
        if len(calls) >= MAX_AGENT_CALLS:
            truncated |= len(current.call_sites) > len(calls)
            break
    return calls, targets, len(current.call_sites), truncated, has_syntax_errors


def _from_call_site(call: CodeCallSite, candidate_ids: tuple[uuid.UUID, ...]) -> _Call:
    return _Call(
        id=call.id,
        caller_id=call.caller_id,
        receiver=call.receiver,
        callee_name=call.callee_name,
        expression=call.expression,
        line=call.line,
        column=call.column,
        quote=call.quote,
        candidate_ids=candidate_ids,
    )


def _java_candidates(
    source: SourceDocument, related: list[SourceDocument],
) -> tuple[list[_Call], dict[uuid.UUID, _Target], int, bool, bool]:
    structure = analyze_java(
        source.content,
        source_id=source.id,
        source_path=source.relative_path or source.original_name,
        related_sources=[JavaSourceInput(
            source_id=item.id,
            source_path=item.relative_path or item.original_name,
            content=item.content,
        ) for item in related],
    )
    targets: dict[uuid.UUID, _Target] = {}
    for item in related:
        for symbol in java_symbols(item.content, source_id=item.id)[0]:
            if symbol.kind == "method":
                candidate = _target(item, symbol)
                targets[candidate.id] = candidate
    calls = []
    for call in structure.cross_file_calls[:MAX_AGENT_CALLS]:
        valid_targets = tuple(target_id for target_id in call.target_ids if target_id in targets)
        if not valid_targets:
            continue
        calls.append(_Call(
            id=call.id,
            caller_id=call.caller_id,
            receiver=call.receiver,
            callee_name=call.callee_name,
            expression=f"{call.receiver}.{call.callee_name}",
            line=call.line,
            column=1,
            quote=_line(source.content, call.line),
            candidate_ids=valid_targets,
        ))
    return calls, targets, len(structure.cross_file_calls), structure.truncated, False


def analyze_calls(db, **kwargs):
    from app.services.agent_workflows import analyze_code
    return analyze_code(db, **kwargs)


def analyze_snapshot(*, source, related, settings, strategy="single_step", related_truncated=False):
    if strategy == 'semantic':
        return _semantic_analysis(source, related, related_truncated)
    if strategy not in {"single_step", "tools"}:
        raise AppError(status_code=422, code="CALL_AGENT_STRATEGY_INVALID", message="不支持的 Agent 分析模式")
    prompt_version = call_tools.PROMPT_VERSION if strategy == "tools" else deepseek.CALL_AGENT_PROMPT_VERSION
    if source.source_type == "java":
        calls, targets, detected, truncated, syntax_errors = _java_candidates(source, related)
    else:
        calls, targets, detected, truncated, syntax_errors = _non_java_candidates(source, related)
    truncated |= related_truncated

    if not calls:
        return AgentCallAnalysisRead(
            source_id=source.id, language=source.source_type, model=None,
            prompt_version=prompt_version,
            calls=[], related_symbols=[], scanned_source_count=1 + len(related),
            detected_call_count=detected, candidate_call_count=0,
            provider_call_count=0, truncated=truncated, has_syntax_errors=syntax_errors,
            strategy=strategy,
        )

    payload = {
        "language": source.source_type,
        "source": {
            "id": str(source.id),
            "path": source.relative_path or source.original_name,
            "excerpt": _excerpt(source.content, {call.line for call in calls}),
        },
        "calls": [{
            "id": str(call.id),
            "caller_id": str(call.caller_id) if call.caller_id else None,
            "expression": call.expression,
            "receiver": call.receiver,
            "callee_name": call.callee_name,
            "line": call.line,
            "quote": call.quote,
            "candidates": [{
                "id": str(target_id),
                "source_id": str(targets[target_id].source_id),
                "path": targets[target_id].source_path,
                "language": targets[target_id].language,
                "qualified_name": targets[target_id].qualified_name,
                "line": targets[target_id].start_line,
                "quote": targets[target_id].quote,
            } for target_id in call.candidate_ids],
        } for call in calls],
    }
    if len(json.dumps(payload, ensure_ascii=False)) > settings.extraction_max_input_chars:
        raise AppError(
            status_code=413, code="CALL_AGENT_INPUT_TOO_LARGE",
            message="跨文件候选上下文过大，请缩小文件或仓库范围",
        )
    try:
        if strategy == "tools":
            draft, provider_count, trace = call_tools.analyze_with_tools(settings, payload, sources=[source, *related], targets=targets)
        else:
            draft = invoke_model(deepseek.analyze_cross_file_calls, settings, payload)
            provider_count, trace = 1, []
    except deepseek.CallAgentError as exc:
        status = 503 if exc.code in {"CALL_AGENT_NOT_CONFIGURED", "CALL_AGENT_PROVIDER_FAILED"} else 502
        raise AppError(status_code=status, code=exc.code, message=exc.message) from exc

    call_by_id = {call.id: call for call in calls}
    decision_by_id = {item.call_id: item for item in draft.decisions}
    if len(decision_by_id) != len(draft.decisions) or set(decision_by_id) != set(call_by_id):
        raise AppError(
            status_code=502, code="CALL_AGENT_OUTPUT_INVALID",
            message="Agent 未完整返回当前调用候选，请重试",
        )
    result_calls: list[AgentCrossFileCallRead] = []
    visible_targets: set[uuid.UUID] = set()
    for call in calls:
        decision = decision_by_id[call.id]
        if not set(decision.target_ids).issubset(call.candidate_ids):
            raise AppError(
                status_code=502, code="CALL_AGENT_EVIDENCE_INVALID",
                message="Agent 返回了候选范围之外的调用目标，本次结果已拒绝",
            )
        visible_targets.update(decision.target_ids)
        result_calls.append(AgentCrossFileCallRead(
            id=call.id, caller_id=call.caller_id, target_ids=decision.target_ids,
            receiver=call.receiver, callee_name=call.callee_name,
            line=call.line, column=call.column, call_quote=call.quote,
            resolution=decision.resolution, confidence=decision.confidence,
            resolution_basis=decision.resolution_basis,
        ))

    return AgentCallAnalysisRead(
        source_id=source.id, language=source.source_type,
        model=settings.deepseek_model, prompt_version=prompt_version,
        calls=result_calls,
        related_symbols=[AgentRelatedSymbolRead(**vars(targets[target_id])) for target_id in sorted(
            visible_targets, key=lambda item: (
                targets[item].source_path.casefold(), targets[item].start_line, str(item),
            ),
        )],
        scanned_source_count=1 + len(related), detected_call_count=detected,
        candidate_call_count=len(calls), provider_call_count=provider_count,
        truncated=truncated, has_syntax_errors=syntax_errors,
        strategy=strategy, tool_call_count=len(trace), tool_trace=trace,
        candidate_generation='syntax-and-import-bindings',
        uncovered_call_count=max(0, detected-len(calls)),
    )


def _semantic_analysis(source, related, related_truncated):
    result = code_semantics.analyze(source, related)
    targets = {}
    for item in [source, *related]:
        symbols = java_symbols(item.content, source_id=item.id)[0] if item.source_type == 'java' else analyze_code(
            item.content, source_id=item.id, language=item.source_type).symbols
        for symbol in symbols:
            if symbol.kind == 'method':
                target = _target(item,symbol)
                targets[target.id] = target
    calls=[]
    selected={}
    sources_by_path={(item.relative_path or item.original_name):item for item in [source,*related]}
    for call in result['calls'][:MAX_AGENT_CALLS]:
        declaration=call.get('target')
        candidates=[] if not declaration else [item for item in targets.values()
            if item.source_path == declaration['path'] and item.start_line <= declaration['line'] <= item.end_line
            and (not declaration.get('name') or item.name == declaration['name'])]
        # Exact declaration identity must survive mapping back to stored immutable source evidence.
        candidates=sorted(candidates,key=lambda item:(item.end_line-item.start_line,str(item.id)))
        target=candidates[0] if candidates and (len(candidates)==1 or
            candidates[0].end_line-candidates[0].start_line < candidates[1].end_line-candidates[1].start_line) else None
        if declaration and declaration.get('name') and (target is None or declaration.get('identity')):
            owner=sources_by_path.get(declaration['path'])
            start,end=declaration['line'],declaration.get('end_line',declaration['line'])
            lines=owner.content.splitlines() if owner else []
            name=declaration['name']
            if owner and 1<=start<=end<=len(lines) and name in '\n'.join(lines[start-1:end]):
                # Compiler declarations can cover valid syntax omitted by the bounded outline parser.
                target=_Target(id=uuid.uuid5(owner.id,f"native-declaration-v1:{start}:{end}:{name}:{declaration.get('identity','')}"),source_id=owner.id,
                    source_path=declaration['path'],language=owner.source_type,name=name,qualified_name=name,
                    start_line=start,end_line=end,quote=lines[start-1])
        if target is not None:
            selected[target.id]=target
        expression=call['expression']
        receiver,_,name=expression.rpartition('.')
        calls.append(AgentCrossFileCallRead(id=uuid.uuid5(source.id,f"native:{call['line']}:{call['column']}:{expression}"),
            caller_id=None,target_ids=[target.id] if target else [],receiver=receiver or None,callee_name=name,
            line=call['line'],column=call['column'],call_quote=_line(source.content,call['line']),
            resolution='resolved' if target else 'unresolved',confidence=1.0 if target else 0,
            resolution_basis='编译器在当前源码上下文中定位声明；不代表运行时动态分派。' if target else '当前源码上下文中未找到可核验的仓库内声明。'))
    return AgentCallAnalysisRead(source_id=source.id,language=source.source_type,model=None,
        prompt_version='native-semantics-v1',calls=calls,related_symbols=[AgentRelatedSymbolRead(**vars(item)) for item in selected.values()],
        scanned_source_count=1+len(related),detected_call_count=len(result['calls']),candidate_call_count=len(calls),
        provider_call_count=0,truncated=related_truncated or result['truncated'] or len(result['calls'])>MAX_AGENT_CALLS,
        has_syntax_errors=any(item.get('kind')=='syntax' for item in result['diagnostics']),strategy='semantic',candidate_generation=result['engine'],
        uncovered_call_count=sum(not item.target_ids for item in calls),semantic_diagnostics=result['diagnostics'])
