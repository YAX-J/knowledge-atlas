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
CONTROL_WORDS = {"if", "for", "while", "switch", "catch", "try", "do", "new", "return", "throw"}


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


def _sanitized(content: str) -> str:
    """Blank comments and literals while preserving offsets and newlines."""
    chars = list(content)
    index = 0
    state = "code"
    while index < len(chars):
        current = chars[index]
        following = chars[index + 1] if index + 1 < len(chars) else ""
        if state == "code":
            if content.startswith('"""', index):
                chars[index:index + 3] = [" ", " ", " "]
                index += 3
                state = "text_block"
                continue
            if current == "/" and following == "/":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "line_comment"
                continue
            if current == "/" and following == "*":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "block_comment"
                continue
            if current in {'"', "'"}:
                quote = current
                chars[index] = " "
                index += 1
                state = "string" if quote == '"' else "char"
                continue
        elif state == "line_comment":
            if current in "\r\n":
                state = "code"
            else:
                chars[index] = " "
        elif state == "block_comment":
            if current == "*" and following == "/":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "code"
                continue
            if current not in "\r\n":
                chars[index] = " "
        elif state == "text_block":
            if content.startswith('"""', index):
                chars[index:index + 3] = [" ", " ", " "]
                index += 3
                state = "code"
                continue
            if current not in "\r\n":
                chars[index] = " "
        else:
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
    return "".join(chars)


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


def parse_java(content: str, *, source_id: uuid.UUID) -> list[JavaChunk]:
    lines = content.splitlines(keepends=True)
    if not lines:
        return []
    sanitized = _sanitized(content)
    depths = _depths(sanitized)
    newlines = [index for index, character in enumerate(content) if character == "\n"]

    def line_number(offset: int) -> int:
        return bisect_right(newlines, max(0, offset)) + 1

    types: list[tuple[int, int, str, int, int]] = []
    for match in TYPE_DECLARATION.finditer(sanitized):
        if depths[match.start()] != 0:
            continue
        opening = sanitized.find("{", match.end())
        if opening < 0:
            continue
        semicolon = sanitized.find(";", match.end(), opening)
        if semicolon >= 0:
            continue
        closing = _closing_brace(sanitized, opening)
        types.append((match.start(), closing, match.group("name"), opening, depths[opening] + 1))

    sections: list[tuple[int, int, str, list[str]]] = []
    cursor_line = 1
    for type_start, type_end, type_name, opening, member_depth in types:
        type_start_line, type_end_line = line_number(type_start), line_number(type_end)
        if cursor_line < type_start_line:
            sections.append((cursor_line, type_start_line - 1, "code", []))
        methods: list[tuple[int, int, str]] = []
        for match in METHOD_DECLARATION.finditer(sanitized, opening + 1, type_end):
            if depths[match.start()] != member_depth or match.group("name") in CONTROL_WORDS:
                continue
            if "new" in match.group("prefix").split():
                continue
            end_offset = match.end() - 1
            if match.group("end") == "{":
                end_offset = _closing_brace(sanitized, end_offset)
            methods.append((line_number(match.start()), line_number(end_offset), match.group("name")))
        member_line = type_start_line
        for method_start, method_end, method_name in methods:
            if member_line < method_start:
                sections.append((member_line, method_start - 1, "type", [type_name]))
            sections.append((method_start, method_end, "method", [type_name, method_name]))
            member_line = method_end + 1
        if member_line <= type_end_line:
            sections.append((member_line, type_end_line, "type", [type_name]))
        cursor_line = type_end_line + 1
    if cursor_line <= len(lines):
        sections.append((cursor_line, len(lines), "code", []))

    chunks: list[JavaChunk] = []
    for start_line, end_line, kind, heading_path in sections:
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
