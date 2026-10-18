"""Bounded, line-preserving Java structure parser without third-party parsers."""

import hashlib
import re
import uuid
from bisect import bisect_right
from dataclasses import dataclass


TYPE_DECLARATION = re.compile(
    r"(?m)^[ \t]*(?:(?:public|protected|private|abstract|static|final|sealed|non-sealed|strictfp)\s+)*"
    r"(?P<kind>@interface|class|interface|enum|record)\s+(?P<name>[A-Za-z_$][\w$]*)\b"
)
METHOD_DECLARATION = re.compile(
    r"(?m)^[ \t]*(?:@[A-Za-z_$][\w$]*(?:\s*\([^;{}]*?\))?\s*)*"
    r"(?P<prefix>(?:(?:public|protected|private|static|final|abstract|synchronized|native|default|strictfp)\s+)*"
    r"(?:<[^;{}]+>\s+)?(?:[A-Za-z_$][\w$\.<>?,\[\]]*\s+)?)"
    r"(?P<name>[A-Za-z_$][\w$]*)\s*\((?P<params>[^;{}]*)\)\s*"
    r"(?:throws\s+[^;{]+)?(?P<end>[{;])"
)
FIELD_DECLARATION = re.compile(
    r"(?m)^[ \t]*(?:@[A-Za-z_$][\w$]*(?:\s*\([^;{}]*?\))?\s*)*"
    r"(?:(?:public|protected|private|static|final|transient|volatile)\s+)*"
    r"(?P<type>[A-Za-z_$][\w$\.<>?,\[\]& \t]*)\s+"
    r"(?P<name>[A-Za-z_$][\w$]*)(?P<tail>[^;{}]*);"
)
LOCAL_CALL = re.compile(
    r"(?<![\w$.])(?:(?:this)\s*\.\s*)?(?P<name>[A-Za-z_$][\w$]*)\s*\("
)
CONTROL_WORDS = {"if", "for", "while", "switch", "catch", "try", "do", "new", "return", "throw"}
MAX_STRUCTURE_SYMBOLS = 200
MAX_STRUCTURE_CALLS = 500


@dataclass(frozen=True)
class JavaChunk:
    id: uuid.UUID
    position: int
    kind: str
    heading_path: list[str]
    start_line: int
    end_line: int
    content: str
    content_sha256: str


@dataclass(frozen=True)
class JavaSymbol:
    id: uuid.UUID
    kind: str
    name: str
    qualified_name: str
    owner: str | None
    start_line: int
    end_line: int


@dataclass(frozen=True)
class JavaCall:
    id: uuid.UUID
    caller_id: uuid.UUID
    callee_ids: list[uuid.UUID]
    callee_name: str
    line: int
    resolution: str


@dataclass(frozen=True)
class JavaStructure:
    symbols: list[JavaSymbol]
    calls: list[JavaCall]
    truncated: bool


@dataclass(frozen=True)
class _TypeDeclaration:
    name: str
    start: int
    opening: int
    end: int
    member_depth: int


@dataclass(frozen=True)
class _MethodDeclaration:
    owner: str
    name: str
    start: int
    opening: int | None
    end: int


def _lex_java(content: str) -> tuple[str, set[int]]:
    """Blank comments/literals and identify comment-only lines without moving offsets."""
    chars = list(content)
    line_has_comment = [False] * (content.count("\n") + 1)
    line_has_code = [False] * len(line_has_comment)
    line_index = 0
    index = 0
    state = "code"
    while index < len(chars):
        current = chars[index]
        following = chars[index + 1] if index + 1 < len(chars) else ""
        if state == "code":
            if content.startswith('"""', index):
                line_has_code[line_index] = True
                chars[index:index + 3] = [" ", " ", " "]
                index += 3
                state = "text_block"
                continue
            if current == "/" and following == "/":
                line_has_comment[line_index] = True
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "line_comment"
                continue
            if current == "/" and following == "*":
                line_has_comment[line_index] = True
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "block_comment"
                continue
            if current in {'"', "'"}:
                line_has_code[line_index] = True
                quote = current
                chars[index] = " "
                index += 1
                state = "string" if quote == '"' else "char"
                continue
            if current == "\n":
                line_index += 1
            elif not current.isspace():
                line_has_code[line_index] = True
        elif state == "line_comment":
            line_has_comment[line_index] = True
            if current in "\r\n":
                state = "code"
                if current == "\n":
                    line_index += 1
            else:
                chars[index] = " "
        elif state == "block_comment":
            line_has_comment[line_index] = True
            if current == "*" and following == "/":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "code"
                continue
            if current == "\n":
                line_index += 1
            elif current != "\r":
                chars[index] = " "
        elif state == "text_block":
            if content.startswith('"""', index):
                line_has_code[line_index] = True
                chars[index:index + 3] = [" ", " ", " "]
                index += 3
                state = "code"
                continue
            if current == "\n":
                line_index += 1
            elif current != "\r":
                if not current.isspace():
                    line_has_code[line_index] = True
                chars[index] = " "
        else:
            if current == "\n":
                line_index += 1
                index += 1
                continue
            if current != "\r" and not current.isspace():
                line_has_code[line_index] = True
            if current == "\\":
                chars[index] = " "
                if index + 1 < len(chars) and chars[index + 1] not in "\r\n":
                    chars[index + 1] = " "
                    index += 2
                    continue
            elif (state == "string" and current == '"') or (state == "char" and current == "'"):
                chars[index] = " "
                state = "code"
            elif current not in "\r\n":
                chars[index] = " "
        index += 1
    comment_only_lines = {
        line + 1
        for line, (has_comment, has_code) in enumerate(zip(line_has_comment, line_has_code))
        if has_comment and not has_code
    }
    return "".join(chars), comment_only_lines


def _depths(text: str) -> list[int]:
    depths = [0] * (len(text) + 1)
    depth = 0
    for index, character in enumerate(text):
        depths[index] = depth
        if character == "{":
            depth += 1
        elif character == "}":
            depth = max(0, depth - 1)
    depths[len(text)] = depth
    return depths


def _closing_brace(text: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return len(text) - 1


def _declarations(text: str) -> list[tuple[_TypeDeclaration, list[_MethodDeclaration]]]:
    depths = _depths(text)
    result: list[tuple[_TypeDeclaration, list[_MethodDeclaration]]] = []
    for match in TYPE_DECLARATION.finditer(text):
        if depths[match.start()] != 0:
            continue
        opening = text.find("{", match.end())
        if opening < 0 or text.find(";", match.end(), opening) >= 0:
            continue
        closing = _closing_brace(text, opening)
        type_declaration = _TypeDeclaration(
            name=match.group("name"), start=match.start(), opening=opening,
            end=closing, member_depth=depths[opening] + 1,
        )
        methods: list[_MethodDeclaration] = []
        for method_match in METHOD_DECLARATION.finditer(text, opening + 1, closing):
            if depths[method_match.start()] != type_declaration.member_depth:
                continue
            method_name = method_match.group("name")
            if method_name in CONTROL_WORDS or "new" in method_match.group("prefix").split():
                continue
            end_offset = method_match.end() - 1
            method_opening = end_offset if method_match.group("end") == "{" else None
            if method_opening is not None:
                end_offset = _closing_brace(text, method_opening)
            methods.append(_MethodDeclaration(
                owner=type_declaration.name, name=method_name,
                start=method_match.start(), opening=method_opening, end=end_offset,
            ))
        result.append((type_declaration, methods))
    return result


def _line_resolver(content: str):
    newlines = [index for index, character in enumerate(content) if character == "\n"]

    def resolve(offset: int) -> int:
        return bisect_right(newlines, max(0, offset)) + 1

    return resolve


def _type_start_line(lines: list[str], declaration_line: int) -> int:
    start_line = declaration_line
    while start_line > 1 and lines[start_line - 2].lstrip().startswith("@"):
        start_line -= 1
    return start_line


def parse_java(content: str, *, source_id: uuid.UUID) -> list[JavaChunk]:
    lines = content.splitlines(keepends=True)
    if not lines:
        return []
    sanitized, comment_only_lines = _lex_java(content)
    line_number = _line_resolver(content)
    declarations = _declarations(sanitized)

    sections: list[tuple[int, int, str, list[str]]] = []
    cursor_line = 1
    for type_declaration, methods in declarations:
        declaration_line = line_number(type_declaration.start)
        type_start_line = _type_start_line(lines, declaration_line)
        type_end_line = line_number(type_declaration.end)
        if cursor_line < type_start_line:
            sections.append((cursor_line, type_start_line - 1, "code", []))
        member_line = type_start_line
        for method in methods:
            method_start = line_number(method.start)
            method_end = line_number(method.end)
            if member_line < method_start:
                sections.append((member_line, method_start - 1, "type", [type_declaration.name]))
            sections.append((
                method_start, method_end, "method", [type_declaration.name, method.name]
            ))
            member_line = method_end + 1
        if member_line <= type_end_line:
            sections.append((member_line, type_end_line, "type", [type_declaration.name]))
        cursor_line = type_end_line + 1
    if cursor_line <= len(lines):
        sections.append((cursor_line, len(lines), "code", []))

    refined_sections: list[tuple[int, int, str, list[str]]] = []
    for start_line, end_line, kind, heading_path in sections:
        if kind == "method":
            refined_sections.append((start_line, end_line, kind, heading_path))
            continue
        group_start = start_line
        group_kind = "comment" if start_line in comment_only_lines else kind
        for current_line in range(start_line + 1, end_line + 1):
            current_kind = "comment" if current_line in comment_only_lines else kind
            if current_kind != group_kind:
                refined_sections.append((group_start, current_line - 1, group_kind, heading_path))
                group_start, group_kind = current_line, current_kind
        refined_sections.append((group_start, end_line, group_kind, heading_path))

    chunks: list[JavaChunk] = []
    for start_line, end_line, kind, heading_path in refined_sections:
        text = "".join(lines[start_line - 1:end_line])
        if not text.strip():
            continue
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        chunks.append(JavaChunk(
            id=uuid.uuid5(source_id, f"{start_line}:{end_line}:{kind}:{digest}"),
            position=len(chunks), kind=kind, heading_path=heading_path,
            start_line=start_line, end_line=end_line, content=text,
            content_sha256=digest,
        ))
    return chunks


def analyze_java(content: str, *, source_id: uuid.UUID) -> JavaStructure:
    """Return a bounded, read-only symbol and same-file call view for one Java source."""
    if not content:
        return JavaStructure(symbols=[], calls=[], truncated=False)
    sanitized, _ = _lex_java(content)
    depths = _depths(sanitized)
    lines = content.splitlines(keepends=True)
    line_number = _line_resolver(content)
    declarations = _declarations(sanitized)
    symbols: list[JavaSymbol] = []
    method_records: list[tuple[_MethodDeclaration, JavaSymbol]] = []

    for type_declaration, methods in declarations:
        type_start = _type_start_line(lines, line_number(type_declaration.start))
        type_end = line_number(type_declaration.end)
        type_symbol = JavaSymbol(
            id=uuid.uuid5(source_id, f"symbol:type:{type_declaration.name}:{type_start}:{type_end}"),
            kind="type", name=type_declaration.name, qualified_name=type_declaration.name,
            owner=None, start_line=type_start, end_line=type_end,
        )
        symbols.append(type_symbol)

        method_ranges = [(method.start, method.end) for method in methods]
        for field_match in FIELD_DECLARATION.finditer(
            sanitized, type_declaration.opening + 1, type_declaration.end
        ):
            if depths[field_match.start()] != type_declaration.member_depth:
                continue
            if any(start <= field_match.start() <= end for start, end in method_ranges):
                continue
            tail = field_match.group("tail")
            before_initializer = tail.split("=", 1)[0]
            if "(" in before_initializer:
                continue
            field_name = field_match.group("name")
            field_start, field_end = line_number(field_match.start()), line_number(field_match.end() - 1)
            qualified_name = f"{type_declaration.name}.{field_name}"
            symbols.append(JavaSymbol(
                id=uuid.uuid5(source_id, f"symbol:field:{qualified_name}:{field_start}:{field_end}"),
                kind="field", name=field_name, qualified_name=qualified_name,
                owner=type_declaration.name, start_line=field_start, end_line=field_end,
            ))

        for method in methods:
            method_start, method_end = line_number(method.start), line_number(method.end)
            qualified_name = f"{type_declaration.name}.{method.name}"
            method_symbol = JavaSymbol(
                id=uuid.uuid5(source_id, f"symbol:method:{qualified_name}:{method_start}:{method_end}"),
                kind="method", name=method.name, qualified_name=qualified_name,
                owner=type_declaration.name, start_line=method_start, end_line=method_end,
            )
            symbols.append(method_symbol)
            method_records.append((method, method_symbol))

    methods_by_owner_name: dict[tuple[str, str], list[JavaSymbol]] = {}
    for _, method_symbol in method_records:
        methods_by_owner_name.setdefault(
            (method_symbol.owner or "", method_symbol.name), []
        ).append(method_symbol)

    kind_order = {"type": 0, "field": 1, "method": 2}
    symbols.sort(key=lambda item: (
        item.start_line, kind_order.get(item.kind, 99), item.end_line, item.qualified_name
    ))

    calls: list[JavaCall] = []
    seen_calls: set[tuple[uuid.UUID, str, int]] = set()
    for method, caller in method_records:
        if method.opening is None:
            continue
        for call_match in LOCAL_CALL.finditer(sanitized, method.opening + 1, method.end):
            callee_name = call_match.group("name")
            targets = methods_by_owner_name.get((caller.owner or "", callee_name), [])
            if not targets or callee_name in CONTROL_WORDS:
                continue
            prefix = sanitized[max(method.opening + 1, call_match.start() - 12):call_match.start()]
            if re.search(r"\bnew\s*$", prefix):
                continue
            call_line = line_number(call_match.start())
            call_key = (caller.id, callee_name, call_line)
            if call_key in seen_calls:
                continue
            seen_calls.add(call_key)
            resolution = "resolved" if len(targets) == 1 else "ambiguous"
            calls.append(JavaCall(
                id=uuid.uuid5(source_id, f"call:{caller.id}:{callee_name}:{call_line}"),
                caller_id=caller.id, callee_ids=[target.id for target in targets],
                callee_name=callee_name, line=call_line, resolution=resolution,
            ))

    visible_symbols = symbols[:MAX_STRUCTURE_SYMBOLS]
    visible_symbol_ids = {symbol.id for symbol in visible_symbols}
    visible_calls = [
        call for call in calls
        if call.caller_id in visible_symbol_ids
        and all(callee_id in visible_symbol_ids for callee_id in call.callee_ids)
    ]
    truncated = len(symbols) > MAX_STRUCTURE_SYMBOLS or len(visible_calls) > MAX_STRUCTURE_CALLS
    return JavaStructure(
        symbols=visible_symbols, calls=visible_calls[:MAX_STRUCTURE_CALLS],
        truncated=truncated,
    )
