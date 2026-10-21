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
PACKAGE_DECLARATION = re.compile(
    r"(?m)^[ \t]*package\s+(?P<name>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*;"
)
IMPORT_DECLARATION = re.compile(
    r"(?m)^[ \t]*import\s+(?!static\b)(?P<name>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)(?P<wildcard>\.\*)?\s*;"
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
VAR_LOCAL_DECLARATION = re.compile(
    r"(?m)^[ \t]*(?:final\s+)?var\s+(?P<name>[A-Za-z_$][\w$]*)\s*="
)
CONSTRUCTOR_INITIALIZER = re.compile(
    r"\s*new\s+(?P<type>[A-Za-z_$][\w$]*"
    r"(?:\s*\.\s*[A-Za-z_$][\w$]*)*)\s*"
)
LOCAL_CALL = re.compile(
    r"(?<![\w$.])(?:(?:this)\s*\.\s*)?(?P<name>[A-Za-z_$][\w$]*)\s*\("
)
QUALIFIED_CALL = re.compile(
    r"(?<![\w$])"
    r"(?P<receiver>(?:this\s*\.\s*)?[A-Za-z_$][\w$]*"
    r"(?:\s*\.\s*[A-Za-z_$][\w$]*)*)"
    r"\s*\.\s*(?P<name>[A-Za-z_$][\w$]*)\s*\("
)
CONTROL_WORDS = {"if", "for", "while", "switch", "catch", "try", "do", "new", "return", "throw"}
MAX_STRUCTURE_SYMBOLS = 200
MAX_STRUCTURE_CALLS = 500
MAX_RELATED_TYPES = 400
MAX_TYPE_RELATIONSHIPS = 500
MAX_RELATED_METHODS = 500
MAX_CROSS_FILE_CALLS = 500
MAX_INHERITANCE_VISITS = 256


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
class JavaSourceInput:
    source_id: uuid.UUID
    source_path: str
    content: str


@dataclass(frozen=True)
class JavaRelatedType:
    id: uuid.UUID
    source_id: uuid.UUID
    source_path: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class JavaTypeRelationship:
    id: uuid.UUID
    source_symbol_id: uuid.UUID
    target_ids: list[uuid.UUID]
    target_name: str
    kind: str
    line: int
    resolution: str


@dataclass(frozen=True)
class JavaRelatedMethod:
    id: uuid.UUID
    source_id: uuid.UUID
    source_path: str
    owner_qualified_name: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class JavaCrossFileCall:
    id: uuid.UUID
    caller_id: uuid.UUID
    target_ids: list[uuid.UUID]
    receiver: str
    callee_name: str
    line: int
    resolution: str


@dataclass(frozen=True)
class JavaStructure:
    symbols: list[JavaSymbol]
    calls: list[JavaCall]
    related_types: list[JavaRelatedType]
    type_relationships: list[JavaTypeRelationship]
    related_methods: list[JavaRelatedMethod]
    cross_file_calls: list[JavaCrossFileCall]
    truncated: bool


@dataclass(frozen=True)
class _TypeDeclaration:
    kind: str
    name: str
    start: int
    header_start: int
    opening: int
    end: int
    member_depth: int


@dataclass(frozen=True)
class _MethodDeclaration:
    owner: str
    name: str
    parameters: str
    start: int
    opening: int | None
    end: int
    modifiers: frozenset[str] = frozenset()


@dataclass
class _BlockScope:
    opening: int
    end: int
    parent: int | None
    supported: bool
    header_start: int
    header_bindings: tuple[tuple[str, str | None], ...] | None = None


@dataclass(frozen=True)
class _MethodScopes:
    blocks: list[_BlockScope]
    openings: list[int]
    blocked_starts: list[int]
    blocked_ends: list[int]

    def block_at(self, offset: int) -> _BlockScope:
        index = bisect_right(self.openings, offset) - 1
        while self.blocks[index].end < offset:
            parent = self.blocks[index].parent
            if parent is None:
                break
            index = parent
        return self.blocks[index]

    def allows(self, offset: int) -> bool:
        index = bisect_right(self.blocked_starts, offset) - 1
        return index < 0 or offset >= self.blocked_ends[index]


@dataclass(frozen=True)
class _LocalBinding:
    start: int
    end: int
    type_name: str | None


@dataclass(frozen=True)
class _JavaTypeIndex:
    source_id: uuid.UUID
    source_path: str
    package_name: str
    imports: dict[str, str]
    wildcard_imports: tuple[str, ...]
    types: tuple[JavaRelatedType, ...]
    methods: tuple[JavaRelatedMethod, ...]
    declarations: tuple[_TypeDeclaration, ...]
    sanitized: str
    method_declarations: dict[uuid.UUID, _MethodDeclaration]


def _lex_java(content: str, *, literal_markers: bool = False) -> tuple[str, set[int]]:
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
                if literal_markers:
                    chars[index] = "0"
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
                if literal_markers:
                    chars[index] = "0"
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
            kind=match.group("kind"), name=match.group("name"), start=match.start(),
            header_start=match.end(), opening=opening,
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
                parameters=method_match.group("params"),
                start=method_match.start(), opening=method_opening, end=end_offset,
                modifiers=frozenset(method_match.group("prefix").split()),
            ))
        result.append((type_declaration, methods))
    return result


def _type_symbol_id(
    source_id: uuid.UUID, *, name: str, start_line: int, end_line: int
) -> uuid.UUID:
    return uuid.uuid5(source_id, f"symbol:type:{name}:{start_line}:{end_line}")


def _method_symbol_id(
    source_id: uuid.UUID, *, qualified_name: str, start_line: int, end_line: int
) -> uuid.UUID:
    return uuid.uuid5(
        source_id,
        f"symbol:method:{qualified_name}:{start_line}:{end_line}",
    )


def _split_type_list(value: str) -> list[tuple[str, int]]:
    """Split a Java type list on top-level commas while retaining segment offsets."""
    result: list[tuple[str, int]] = []
    start = 0
    angle_depth = 0
    round_depth = 0
    for index, character in enumerate(value):
        if character == "<":
            angle_depth += 1
        elif character == ">":
            angle_depth = max(0, angle_depth - 1)
        elif character == "(":
            round_depth += 1
        elif character == ")":
            round_depth = max(0, round_depth - 1)
        elif character == "," and angle_depth == 0 and round_depth == 0:
            result.append((value[start:index], start))
            start = index + 1
    result.append((value[start:], start))
    return result


def _referenced_type_name(value: str) -> tuple[str, int] | None:
    match = re.search(
        r"[A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*",
        value,
    )
    if match is None:
        return None
    return re.sub(r"\s+", "", match.group(0)), match.start()


def _heritage_references(
    declaration: _TypeDeclaration, sanitized: str
) -> list[tuple[str, str, int]]:
    header = sanitized[declaration.header_start:declaration.opening]
    clause_pattern = re.compile(
        r"\b(?P<kind>extends|implements)\s+(?P<types>.*?)"
        r"(?=\b(?:implements|permits)\b|$)",
        re.DOTALL,
    )
    references: list[tuple[str, str, int]] = []
    for clause in clause_pattern.finditer(header):
        kind = clause.group("kind")
        type_list = clause.group("types")
        type_list_offset = declaration.header_start + clause.start("types")
        for segment, segment_offset in _split_type_list(type_list):
            referenced = _referenced_type_name(segment)
            if referenced is None:
                continue
            name, name_offset = referenced
            references.append((kind, name, type_list_offset + segment_offset + name_offset))
    return references


def _index_java_source(source: JavaSourceInput) -> _JavaTypeIndex:
    sanitized, _ = _lex_java(source.content, literal_markers=True)
    line_number = _line_resolver(source.content)
    lines = source.content.splitlines(keepends=True)
    package_match = PACKAGE_DECLARATION.search(sanitized)
    package_name = package_match.group("name") if package_match else ""
    imports: dict[str, str] = {}
    wildcard_imports: list[str] = []
    for match in IMPORT_DECLARATION.finditer(sanitized):
        import_name = match.group("name")
        if match.group("wildcard"):
            wildcard_imports.append(import_name)
        else:
            imports[import_name.rsplit(".", 1)[-1]] = import_name

    declaration_pairs = _declarations(sanitized)
    declarations = tuple(item[0] for item in declaration_pairs)
    types: list[JavaRelatedType] = []
    methods: list[JavaRelatedMethod] = []
    method_declarations: dict[uuid.UUID, _MethodDeclaration] = {}
    for declaration, declaration_methods in declaration_pairs:
        start_line = _type_start_line(lines, line_number(declaration.start))
        end_line = line_number(declaration.end)
        owner_qualified_name = (
            f"{package_name}.{declaration.name}" if package_name else declaration.name
        )
        types.append(JavaRelatedType(
            id=_type_symbol_id(
                source.source_id,
                name=declaration.name,
                start_line=start_line,
                end_line=end_line,
            ),
            source_id=source.source_id,
            source_path=source.source_path,
            name=declaration.name,
            qualified_name=owner_qualified_name,
            start_line=start_line,
            end_line=end_line,
        ))
        for method in declaration_methods:
            method_start = line_number(method.start)
            method_end = line_number(method.end)
            local_qualified_name = f"{declaration.name}.{method.name}"
            methods.append(JavaRelatedMethod(
                id=_method_symbol_id(
                    source.source_id,
                    qualified_name=local_qualified_name,
                    start_line=method_start,
                    end_line=method_end,
                ),
                source_id=source.source_id,
                source_path=source.source_path,
                owner_qualified_name=owner_qualified_name,
                name=method.name,
                qualified_name=f"{owner_qualified_name}.{method.name}",
                start_line=method_start,
                end_line=method_end,
            ))
            method_declarations[methods[-1].id] = method
    return _JavaTypeIndex(
        source_id=source.source_id,
        source_path=source.source_path,
        package_name=package_name,
        imports=imports,
        wildcard_imports=tuple(wildcard_imports),
        types=tuple(types),
        methods=tuple(methods),
        declarations=declarations,
        sanitized=sanitized,
        method_declarations=method_declarations,
    )


def _types_by_qualified_name(
    source_indexes: list[_JavaTypeIndex],
) -> dict[str, list[JavaRelatedType]]:
    result: dict[str, list[JavaRelatedType]] = {}
    for index in source_indexes:
        for type_definition in index.types:
            result.setdefault(type_definition.qualified_name, []).append(type_definition)
    return result


def _resolve_type_name(
    current: _JavaTypeIndex,
    target_name: str,
    types_by_qualified_name: dict[str, list[JavaRelatedType]],
) -> list[JavaRelatedType]:
    if "." in target_name:
        return types_by_qualified_name.get(target_name, [])
    if target_name in current.imports:
        return types_by_qualified_name.get(current.imports[target_name], [])
    same_package = (
        f"{current.package_name}.{target_name}"
        if current.package_name else target_name
    )
    targets = types_by_qualified_name.get(same_package, [])
    if targets:
        return targets
    return [
        match
        for package in current.wildcard_imports
        for match in types_by_qualified_name.get(f"{package}.{target_name}", [])
    ]


def _resolve_type_relationships(
    current: _JavaTypeIndex,
    source_indexes: list[_JavaTypeIndex],
    *,
    visible_source_symbol_ids: set[uuid.UUID],
) -> tuple[list[JavaRelatedType], list[JavaTypeRelationship], bool]:
    types_by_qualified_name = _types_by_qualified_name(source_indexes)

    related_by_id: dict[uuid.UUID, JavaRelatedType] = {}
    relationships: list[JavaTypeRelationship] = []
    line_number = _line_resolver(current.sanitized)
    current_types_by_name = {item.name: item for item in current.types}
    for declaration in current.declarations:
        source_type = current_types_by_name.get(declaration.name)
        if (
            source_type is None
            or source_type.id not in visible_source_symbol_ids
        ):
            continue
        for kind, target_name, target_offset in _heritage_references(
            declaration, current.sanitized
        ):
            targets = _resolve_type_name(
                current,
                target_name,
                types_by_qualified_name,
            )
            targets = [
                target
                for target in targets
                if target.source_id != current.source_id
            ]
            if not targets:
                continue

            target_ids = [target.id for target in targets]
            for target in targets:
                related_by_id[target.id] = target
            relationship_line = line_number(target_offset)
            relationships.append(JavaTypeRelationship(
                id=uuid.uuid5(
                    current.source_id,
                    f"type-relationship:{source_type.id}:{kind}:{target_name}:{relationship_line}",
                ),
                source_symbol_id=source_type.id,
                target_ids=target_ids,
                target_name=target_name,
                kind=kind,
                line=relationship_line,
                resolution="resolved" if len(targets) == 1 else "ambiguous",
            ))

    related_types = sorted(
        related_by_id.values(),
        key=lambda item: (item.source_path, item.start_line, item.qualified_name, str(item.id)),
    )
    relationships.sort(key=lambda item: (item.line, item.kind, item.target_name, str(item.id)))
    truncated = (
        len(related_types) > MAX_RELATED_TYPES
        or len(relationships) > MAX_TYPE_RELATIONSHIPS
    )
    visible_related_types = related_types[:MAX_RELATED_TYPES]
    visible_target_ids = {item.id for item in visible_related_types}
    visible_relationships = [
        item for item in relationships
        if all(target_id in visible_target_ids for target_id in item.target_ids)
    ][:MAX_TYPE_RELATIONSHIPS]
    referenced_target_ids = {
        target_id
        for relationship in visible_relationships
        for target_id in relationship.target_ids
    }
    visible_related_types = [
        item for item in visible_related_types
        if item.id in referenced_target_ids
    ]
    return visible_related_types, visible_relationships, truncated


def _field_types_by_owner(current: _JavaTypeIndex) -> dict[tuple[str, str], str]:
    depths = _depths(current.sanitized)
    result: dict[tuple[str, str], str] = {}
    for declaration, methods in _declarations(current.sanitized):
        method_ranges = [(method.start, method.end) for method in methods]
        for field_match in FIELD_DECLARATION.finditer(
            current.sanitized,
            declaration.opening + 1,
            declaration.end,
        ):
            if depths[field_match.start()] != declaration.member_depth:
                continue
            if any(start <= field_match.start() <= end for start, end in method_ranges):
                continue
            before_initializer = field_match.group("tail").split("=", 1)[0]
            if "(" in before_initializer:
                continue
            declared_type = field_match.group("type")
            if len(_split_type_list(declared_type)) != 1:
                continue
            referenced = _referenced_type_name(declared_type)
            if referenced is not None:
                result[(declaration.name, field_match.group("name"))] = referenced[0]
    return result


def _parameter_types(parameters: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for segment, _ in _split_type_list(parameters):
        name_match = re.search(
            r"(?P<name>[A-Za-z_$][\w$]*)\s*(?:\[\s*\])?\s*$",
            segment,
        )
        if name_match is None:
            continue
        declaration = segment[:name_match.start()]
        declaration = re.sub(
            r"@[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*"
            r"(?:\s*\([^()]*\))?\s*",
            "",
            declaration,
        )
        declaration = re.sub(r"\bfinal\b", "", declaration)
        declaration = re.sub(r"\.\.\.\s*$", "", declaration).strip()
        referenced = _referenced_type_name(declaration)
        if referenced is not None and referenced[0] != "var":
            result[name_match.group("name")] = referenced[0]
    return result


def _constructor_initialized_type(initializer: str) -> str | None:
    """Recognize a complete `new Type<T>(...)` expression, without data flow."""
    match = CONSTRUCTOR_INITIALIZER.match(initializer)
    if match is None or any(char in initializer for char in "{};"):
        return None
    cursor = match.end()
    if cursor < len(initializer) and initializer[cursor] == "<":
        depth = 0
        for cursor in range(cursor, len(initializer)):
            char = initializer[cursor]
            if char == "<":
                depth += 1
            elif char == ">":
                depth -= 1
                if depth == 0:
                    cursor += 1
                    break
            elif not (char.isalnum() or char in "_$.,?[]&@ \t\r\n"):
                return None
        else:
            return None
        while cursor < len(initializer) and initializer[cursor].isspace():
            cursor += 1
    if cursor >= len(initializer) or initializer[cursor] != "(":
        return None
    depth = 0
    for position in range(cursor, len(initializer)):
        if initializer[position] == "(":
            depth += 1
        elif initializer[position] == ")":
            depth -= 1
            if depth == 0:
                if initializer[position + 1:].strip():
                    return None
                return re.sub(r"\s+", "", match.group("type"))
    return None


def _supported_block_header(header: str) -> bool:
    header = header.strip()
    if header in {"", "else", "try", "finally"}:
        return True
    match = re.match(r"(?:else\s+)?(?:if|while)\s*\(", header)
    if match is None or re.search(r"\binstanceof\b", header):
        return False
    depth = 1
    for position in range(match.end(), len(header)):
        if header[position] == "(":
            depth += 1
        elif header[position] == ")":
            depth -= 1
            if depth == 0:
                return not header[position + 1:].strip()
    return False


def _enhanced_for_variable(header: str) -> tuple[str, str | None] | None:
    """Recognize a single enhanced-for binding, without element-type inference."""
    match = re.fullmatch(
        r"\s*for\s*\(\s*(?:final\s+)?"
        r"(?P<type>[A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*"
        r"(?:\s*<[\w$.,?<>\[\]&\s]+>)?(?:\s*\[\s*\])*)\s+"
        r"(?P<name>[A-Za-z_$][\w$]*)(?P<array>(?:\s*\[\s*\])*)\s*:\s*"
        r"(?P<iterable>[^;{}]+)\)\s*",
        header,
    )
    if match is None or re.search(r"\binstanceof\b", header):
        return None
    depth = 0
    for char in match.group("iterable"):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return None
    if depth != 0 or not match.group("iterable").strip():
        return None
    declared_type = match.group("type")
    referenced = _referenced_type_name(declared_type)
    type_name = referenced[0] if referenced is not None else None
    if type_name == "var" or re.search(r"\]\s*$", declared_type) or match.group("array"):
        type_name = None
    return match.group("name"), type_name


def _catch_variable(header: str) -> tuple[str, str | None] | None:
    """Read an unannotated catch parameter; union types remain unknown."""
    qualified_type = r"[A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*"
    match = re.fullmatch(
        r"\s*catch\s*\(\s*(?:final\s+)?"
        rf"(?P<type>{qualified_type}(?:\s*\|\s*{qualified_type})*)\s+"
        r"(?P<name>[A-Za-z_$][\w$]*)\s*\)\s*",
        header,
    )
    if match is None:
        return None
    declared_type = re.sub(r"\s+", "", match.group("type"))
    type_name = None if "|" in declared_type or declared_type == "var" else declared_type
    return match.group("name"), type_name


def _split_expressions(value: str, separator: str) -> list[str] | None:
    """Split header statements without splitting nested calls or array access."""
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    parts: list[str] = []
    start = 0
    for offset, char in enumerate(value):
        if char in "([{":
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return None
        elif char == separator and not stack:
            parts.append(value[start:offset])
            start = offset + 1
    return None if stack else parts + [value[start:]]


def _header_local(value: str) -> tuple[str, str | None] | None:
    match = re.fullmatch(
        r"\s*(?:final\s+)?"
        r"(?P<type>[A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*"
        r"(?:\s*<[\w$.,?<>\[\]&\s]+>)?(?:\s*\[\s*\])*)\s+"
        r"(?P<name>[A-Za-z_$][\w$]*)(?P<array>(?:\s*\[\s*\])*)\s*="
        r"(?P<initializer>[\s\S]+)", value,
    )
    if match is None:
        return None
    # Multi-declarators are not a single binding, even when the first is typed.
    parts = _split_expressions(match.group("initializer"), ",")
    if parts is None or (len(parts) != 1 and _constructor_initialized_type(match.group("initializer")) is None):
        return None
    declared_type = match.group("type")
    referenced = _referenced_type_name(declared_type)
    type_name = referenced[0] if referenced else None
    if type_name == "var":
        type_name = _constructor_initialized_type(match.group("initializer"))
    if re.search(r"\]\s*$", declared_type) or match.group("array"):
        type_name = None
    return match.group("name"), type_name


def _header_bindings(header: str) -> tuple[tuple[str, str | None], ...] | None:
    single = _enhanced_for_variable(header) or _catch_variable(header)
    if single is not None:
        return (single,)
    match = re.fullmatch(r"\s*(?P<kind>for|try)\s*\((?P<body>[\s\S]*)\)\s*", header)
    if match is None or re.search(r"\binstanceof\b", header):
        return None
    parts = _split_expressions(match.group("body"), ";")
    if parts is None:
        return None
    if match.group("kind") == "for":
        if len(parts) != 3:
            return None
        if not parts[0].strip():
            return ()
        binding = _header_local(parts[0])
        if binding is not None:
            return (binding,)
        # Expression initializers declare no variables. Do not accept a failed
        # declaration (annotations/multiple declarators) as an expression.
        if re.match(r"\s*[A-Za-z_$][\w$]*(?:\s*\.[\w$]+)*\s*(?:=(?!=)|\+\+|--|\()", parts[0]):
            return ()
        return None
    if not parts[-1].strip():
        parts.pop()  # Optional trailing resource separator.
    if not parts:
        return None
    bindings: list[tuple[str, str | None]] = []
    for part in parts:
        binding = _header_local(part)
        if binding is not None:
            bindings.append(binding)
        elif not re.fullmatch(r"\s*(?:this\s*\.\s*)?[A-Za-z_$][\w$]*(?:\s*\.\s*[\w$]+)*\s*", part):
            return None
    return tuple(bindings)


def _method_scopes(text: str, *, opening: int, end: int) -> _MethodScopes:
    """Index supported lexical blocks and exclude bodies with unknown bindings."""
    blocks = [_BlockScope(opening, end, None, True, opening)]
    stack = [0]
    statement_start = opening + 1
    round_depth = 0
    for position in range(opening + 1, end):
        char = text[position]
        if char == "(":
            round_depth += 1
        elif char == ")":
            round_depth -= 1
        elif char == "{":
            parent = stack[-1]
            header = text[statement_start:position]
            header_bindings = _header_bindings(header)
            supported = (
                blocks[parent].supported
                and round_depth == 0
                and (_supported_block_header(header) or header_bindings is not None)
            )
            blocks.append(_BlockScope(
                position, end, parent, supported, statement_start, header_bindings,
            ))
            stack.append(len(blocks) - 1)
            statement_start = position + 1
        elif char == "}":
            if len(stack) > 1:
                blocks[stack.pop()].end = position
            statement_start = position + 1
        elif char == ";" and round_depth == 0:
            statement_start = position + 1

    blocked: list[tuple[int, int]] = []
    for block in sorted(blocks[1:], key=lambda item: item.header_start):
        if block.supported and block.header_bindings is None:
            continue
        # Header variables are only visible in their bodies. Skip header calls
        # rather than guess complex expression bindings.
        blocked_end = block.opening if block.supported else block.end
        if blocked and block.header_start <= blocked[-1][1]:
            blocked[-1] = (blocked[-1][0], max(blocked[-1][1], blocked_end))
        else:
            blocked.append((block.header_start, blocked_end))
    return _MethodScopes(
        blocks=blocks,
        openings=[block.opening for block in blocks],
        blocked_starts=[start for start, _ in blocked],
        blocked_ends=[end for _, end in blocked],
    )


def _local_variable_types(
    current: _JavaTypeIndex,
    method: _MethodDeclaration,
    scopes: _MethodScopes,
) -> dict[str, list[_LocalBinding]]:
    if method.opening is None:
        return {}
    result: dict[str, list[_LocalBinding]] = {}
    for scope in scopes.blocks:
        if scope.supported and scope.header_bindings is not None:
            for name, type_name in scope.header_bindings:
                result.setdefault(name, []).append(_LocalBinding(
                    scope.opening, scope.end, type_name,
                ))
    matches = [
        (match, inferred)
        for pattern, inferred in (
            (FIELD_DECLARATION, False), (VAR_LOCAL_DECLARATION, True),
        )
        for match in pattern.finditer(
            current.sanitized, method.opening + 1, method.end
        )
    ]
    matches.sort(key=lambda item: item[0].start())
    round_depth = 0
    scanned_until = method.opening + 1
    for match, inferred in matches:
        prefix = current.sanitized[scanned_until:match.start()]
        round_depth += prefix.count("(") - prefix.count(")")
        scanned_until = match.start()
        scope = scopes.block_at(match.start())
        if not scope.supported or round_depth != 0:
            continue
        declarations = result.setdefault(match.group("name"), [])
        if not inferred:
            before_initializer = match.group("tail").split("=", 1)[0]
            if "(" in before_initializer or "," in before_initializer:
                continue
            declared_type = match.group("type")
            if len(_split_type_list(declared_type)) != 1:
                continue
            referenced = _referenced_type_name(declared_type)
            if referenced is not None and referenced[0] != "var":
                declarations.append(_LocalBinding(
                    match.start(), scope.end, referenced[0],
                ))
            continue
        # Even an unsupported initializer shadows a field or a type name.
        declarations.append(_LocalBinding(match.start(), scope.end, None))
        terminator = current.sanitized.find(";", match.end(), scope.end)
        if terminator < 0:
            continue
        inferred_type = _constructor_initialized_type(
            current.sanitized[match.end():terminator]
        )
        if inferred_type is not None:
            declarations.append(_LocalBinding(terminator, scope.end, inferred_type))
    for declarations in result.values():
        declarations.sort(key=lambda item: item.start)
    return result


def _call_arity(text: str, opening: int, end: int) -> int | None:
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    count = 0
    has_argument = False
    for char in text[opening + 1:end]:
        if char == ")" and not stack:
            return count + int(has_argument)
        if char in "([{":
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return None
        elif char in "<>" and not stack:
            # Generic argument commas and comparisons need a real expression
            # parser. Preserve candidates instead of narrowing incorrectly.
            return None
        elif char == "," and not stack:
            count += 1
            has_argument = False
            continue
        if not char.isspace():
            has_argument = True
    return None


def _accepts_arity(parameters: str, arity: int | None) -> bool:
    if arity is None:
        return True
    parts = _split_type_list(parameters) if parameters.strip() else []
    if parts and "..." in parts[-1][0]:
        return arity >= len(parts) - 1
    return arity == len(parts)


def _parameter_signature(
    index: _JavaTypeIndex, parameters: str,
    types_by_name: dict[str, list[JavaRelatedType]],
) -> tuple[str, ...]:
    signature: list[str] = []
    for part, _ in _split_type_list(parameters) if parameters.strip() else []:
        part = re.sub(r"@[\w$.]+(?:\s*\([^()]*\))?\s*", "", part)
        part = re.sub(r"\bfinal\b", "", part)
        erased = ""
        depth = 0
        for char in part:
            if char == "<":
                depth += 1
            elif char == ">":
                depth = max(0, depth - 1)
            elif depth == 0:
                erased += char
        referenced = _referenced_type_name(erased)
        if referenced is None:
            signature.append(f"unknown:{index.source_id}:{part}")
            continue
        raw = referenced[0]
        resolved_names = {item.qualified_name for item in _resolve_type_name(index, raw, types_by_name)}
        if len(resolved_names) == 1:
            raw = next(iter(resolved_names))
        elif raw in index.imports:
            raw = index.imports[raw]
        elif "." not in raw and raw not in {"boolean", "byte", "char", "short", "int", "long", "float", "double"}:
            # Keep unresolved wildcard contexts distinct, avoiding guessed
            # overrides between unrelated external types with the same name.
            raw = f"{index.package_name}:{index.wildcard_imports}:{raw}"
        dimensions = len(re.findall(r"\[\s*\]", erased)) + int("..." in erased)
        signature.append(raw + "[]" * dimensions)
    return tuple(signature)


class _MethodLookup:
    """Bounded repository-local candidate lookup, not runtime dispatch."""

    def __init__(self, indexes: list[_JavaTypeIndex]) -> None:
        self.indexes = {index.source_id: index for index in indexes}
        self.types_by_name = _types_by_qualified_name(indexes)
        self.types = {item.id: item for index in indexes for item in index.types}
        self.parents: dict[uuid.UUID, list[JavaRelatedType]] = {}
        self.superclasses: dict[uuid.UUID, list[JavaRelatedType]] = {}
        self.interfaces: set[uuid.UUID] = set()
        self.methods: dict[tuple[uuid.UUID, str, str], list[JavaRelatedMethod]] = {}
        self.signatures: dict[uuid.UUID, tuple[str, ...]] = {}
        self.cache: dict[tuple, list[JavaRelatedMethod]] = {}
        self.truncated = False
        for index in indexes:
            by_name = {item.name: item for item in index.types}
            for declaration in index.declarations:
                owner = by_name[declaration.name]
                if declaration.kind in {"interface", "@interface"}:
                    self.interfaces.add(owner.id)
                for kind, name, _ in _heritage_references(declaration, index.sanitized):
                    parents = _resolve_type_name(index, name, self.types_by_name)
                    self.parents.setdefault(owner.id, []).extend(parents)
                    if kind == "extends" and declaration.kind != "interface":
                        self.superclasses.setdefault(owner.id, []).extend(parents)
            for method in index.methods:
                declaration = index.method_declarations[method.id]
                if declaration.name == declaration.owner:
                    continue  # Constructors are not inherited methods.
                self.methods.setdefault((index.source_id, method.owner_qualified_name, method.name), []).append(method)
                self.signatures[method.id] = _parameter_signature(index, declaration.parameters, self.types_by_name)

    def candidates(
        self, owner: JavaRelatedType, name: str, arity: int | None,
        *, inherited_from: JavaRelatedType | None = None,
    ) -> list[JavaRelatedMethod]:
        cache_key = (owner.id, name, arity, inherited_from.id if inherited_from else None)
        if cache_key in self.cache:
            return self.cache[cache_key]
        pending = [(owner, frozenset(), (inherited_from.id,) if inherited_from else ())]
        seen: set[tuple] = set()
        targets: dict[uuid.UUID, JavaRelatedMethod] = {}
        visits = 0
        while pending:
            current, hidden, path = pending.pop()
            if current.id in path:
                self.truncated = True
                continue
            context = (current.id, hidden, frozenset(self.indexes[self.types[parent].source_id].package_name for parent in path))
            if context in seen:
                continue
            seen.add(context)
            visits += 1
            if visits > MAX_INHERITANCE_VISITS:
                self.truncated = True
                break
            index = self.indexes[current.source_id]
            visible = []
            for method in self.methods.get((current.source_id, current.qualified_name, name), []):
                declaration = index.method_declarations[method.id]
                modifiers = declaration.modifiers
                if path:
                    if "private" in modifiers or (current.id in self.interfaces and "static" in modifiers):
                        continue
                    if not modifiers.intersection({"public", "protected"}) and current.id not in self.interfaces:
                        if any(self.indexes[self.types[parent].source_id].package_name != index.package_name for parent in path):
                            continue
                visible.append(method)
                if self.signatures[method.id] not in hidden and _accepts_arity(declaration.parameters, arity):
                    targets[method.id] = method
            next_hidden = hidden | frozenset(self.signatures[method.id] for method in visible)
            pending.extend((parent, next_hidden, path + (current.id,)) for parent in self.parents.get(current.id, []))
        result = list(targets.values())
        self.cache[cache_key] = result
        return result


def _resolve_cross_file_calls(
    current: _JavaTypeIndex,
    source_indexes: list[_JavaTypeIndex],
    method_records: list[tuple[_MethodDeclaration, JavaSymbol]],
    *,
    visible_source_symbol_ids: set[uuid.UUID],
) -> tuple[list[JavaRelatedMethod], list[JavaCrossFileCall], bool]:
    lookup = _MethodLookup(source_indexes)
    types_by_qualified_name = lookup.types_by_name
    field_types = _field_types_by_owner(current)
    line_number = _line_resolver(current.sanitized)
    related_by_id: dict[uuid.UUID, JavaRelatedMethod] = {}
    calls: list[JavaCrossFileCall] = []
    seen_calls: set[tuple[uuid.UUID, str, str, int]] = set()

    for method, caller in method_records:
        if method.opening is None or caller.id not in visible_source_symbol_ids:
            continue
        parameter_types = _parameter_types(method.parameters)
        scopes = _method_scopes(
            current.sanitized, opening=method.opening, end=method.end,
        )
        local_types = _local_variable_types(current, method, scopes)
        owner = next(item for item in current.types if item.name == method.owner)
        call_matches = [(match, re.sub(r"\s+", "", match.group("receiver")))
                        for match in QUALIFIED_CALL.finditer(current.sanitized, method.opening + 1, method.end)]
        for match in LOCAL_CALL.finditer(current.sanitized, method.opening + 1, method.end):
            if re.match(r"this\s*\.", match.group(0)):
                continue
            prefix = current.sanitized[max(method.opening + 1, match.start() - 12):match.start()]
            if match.group("name") in CONTROL_WORDS or re.search(r"\bnew\s*$", prefix):
                continue
            call_matches.append((match, "this"))
        call_matches.sort(key=lambda item: item[0].start())
        for call_match, receiver in call_matches:
            if not scopes.allows(call_match.start()):
                continue
            callee_name = call_match.group("name")
            if receiver in {"this", "super"}:
                target_type_name = owner.qualified_name
            elif receiver.startswith("this.") and receiver.count(".") == 1:
                field_name = receiver.split(".", 1)[1]
                target_type_name = field_types.get(
                    (caller.owner or "", field_name)
                )
            elif "." not in receiver:
                declarations = local_types.get(receiver, [])
                declaration = next(
                    (
                        binding
                        for binding in reversed(declarations)
                        if binding.start < call_match.start() < binding.end
                    ),
                    None,
                )
                if declaration is not None:
                    target_type_name = declaration.type_name
                    if target_type_name is None:
                        continue
                else:
                    target_type_name = parameter_types.get(receiver)
                if target_type_name is None:
                    target_type_name = field_types.get(
                        (caller.owner or "", receiver)
                    )
            else:
                target_type_name = None
            if target_type_name is None:
                receiver_type_name = receiver.rsplit(".", 1)[-1]
                if (
                    receiver.startswith("this.")
                    or not receiver_type_name[:1].isupper()
                ):
                    continue
                target_type_name = receiver

            if receiver == "this":
                target_types = [owner]  # The current source identity is known.
            elif receiver == "super":
                target_types = lookup.superclasses.get(owner.id, [])
            else:
                target_types = _resolve_type_name(
                    current, target_type_name, types_by_qualified_name,
                )
            arity = _call_arity(current.sanitized, call_match.end() - 1, method.end)
            targets = sorted(
                {target_method.id: target_method
                    for target_type in target_types
                    for target_method in lookup.candidates(
                        target_type, callee_name, arity,
                        inherited_from=owner if receiver == "super" else None,
                    )
                    if target_method.source_id != current.source_id
                }.values(),
                key=lambda item: (
                    item.source_path,
                    item.start_line,
                    item.qualified_name,
                    str(item.id),
                ),
            )
            if not targets:
                continue
            call_line = line_number(call_match.start())
            call_key = (caller.id, receiver, callee_name, call_line)
            if call_key in seen_calls:
                continue
            seen_calls.add(call_key)
            for target in targets:
                related_by_id[target.id] = target
            calls.append(JavaCrossFileCall(
                id=uuid.uuid5(
                    current.source_id,
                    f"cross-file-call:{caller.id}:{receiver}:{callee_name}:{call_line}",
                ),
                caller_id=caller.id,
                target_ids=[target.id for target in targets],
                receiver=receiver,
                callee_name=callee_name,
                line=call_line,
                resolution="resolved" if len(targets) == 1 else "ambiguous",
            ))

    related_methods = sorted(
        related_by_id.values(),
        key=lambda item: (
            item.source_path,
            item.start_line,
            item.qualified_name,
            str(item.id),
        ),
    )
    calls.sort(key=lambda item: (
        item.line,
        item.receiver,
        item.callee_name,
        str(item.id),
    ))
    truncated = (
        len(related_methods) > MAX_RELATED_METHODS
        or len(calls) > MAX_CROSS_FILE_CALLS
        or lookup.truncated
    )
    visible_related_methods = related_methods[:MAX_RELATED_METHODS]
    visible_target_ids = {item.id for item in visible_related_methods}
    visible_calls = [
        item for item in calls
        if all(target_id in visible_target_ids for target_id in item.target_ids)
    ][:MAX_CROSS_FILE_CALLS]
    referenced_target_ids = {
        target_id
        for call in visible_calls
        for target_id in call.target_ids
    }
    visible_related_methods = [
        item for item in visible_related_methods
        if item.id in referenced_target_ids
    ]
    return visible_related_methods, visible_calls, truncated


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


def analyze_java(
    content: str,
    *,
    source_id: uuid.UUID,
    source_path: str = "",
    related_sources: list[JavaSourceInput] | None = None,
    related_sources_truncated: bool = False,
) -> JavaStructure:
    """Return a bounded symbol view using only caller-supplied related sources."""
    if not content:
        return JavaStructure(
            symbols=[],
            calls=[],
            related_types=[],
            type_relationships=[],
            related_methods=[],
            cross_file_calls=[],
            truncated=False,
        )
    sanitized, _ = _lex_java(content, literal_markers=True)
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
            id=_type_symbol_id(
                source_id,
                name=type_declaration.name,
                start_line=type_start,
                end_line=type_end,
            ),
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
                id=_method_symbol_id(
                    source_id,
                    qualified_name=qualified_name,
                    start_line=method_start,
                    end_line=method_end,
                ),
                kind="method", name=method.name, qualified_name=qualified_name,
                owner=type_declaration.name, start_line=method_start, end_line=method_end,
            )
            symbols.append(method_symbol)
            method_records.append((method, method_symbol))

    methods_by_owner_name: dict[tuple[str, str], list[JavaSymbol]] = {}
    declarations_by_id = {symbol.id: declaration for declaration, symbol in method_records}
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
        scopes = _method_scopes(sanitized, opening=method.opening, end=method.end)
        for call_match in LOCAL_CALL.finditer(sanitized, method.opening + 1, method.end):
            if not scopes.allows(call_match.start()):
                continue
            callee_name = call_match.group("name")
            arity = _call_arity(sanitized, call_match.end() - 1, method.end)
            targets = [target for target in methods_by_owner_name.get((caller.owner or "", callee_name), [])
                       if _accepts_arity(declarations_by_id[target.id].parameters, arity)]
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
    current_input = JavaSourceInput(
        source_id=source_id, source_path=source_path, content=content
    )
    inputs = [current_input]
    inputs.extend(
        item for item in (related_sources or []) if item.source_id != source_id
    )
    indexes = [_index_java_source(item) for item in inputs]
    related_types, type_relationships, related_structure_truncated = (
        _resolve_type_relationships(
            indexes[0],
            indexes,
            visible_source_symbol_ids=visible_symbol_ids,
        )
    )
    related_methods, cross_file_calls, related_calls_truncated = (
        _resolve_cross_file_calls(
            indexes[0],
            indexes,
            method_records,
            visible_source_symbol_ids=visible_symbol_ids,
        )
    )
    truncated = (
        len(symbols) > MAX_STRUCTURE_SYMBOLS
        or len(visible_calls) > MAX_STRUCTURE_CALLS
        or related_structure_truncated
        or related_calls_truncated
        or related_sources_truncated
    )
    return JavaStructure(
        symbols=visible_symbols,
        calls=visible_calls[:MAX_STRUCTURE_CALLS],
        related_types=related_types,
        type_relationships=type_relationships,
        related_methods=related_methods,
        cross_file_calls=cross_file_calls,
        truncated=truncated,
    )
