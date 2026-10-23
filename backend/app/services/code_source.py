"""Bounded multi-language outlines and lossless whole-line source partitions.

Tree-sitter is only a syntax boundary: no execution, imports, type inference or
authoritative knowledge writes. Java keeps its existing parser and identities.
"""

import hashlib
import importlib
import uuid
from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache

from tree_sitter import Language, Node, Parser

from app.services.java_source import JavaChunk, JavaSymbol


MAX_SYMBOLS = 200
MAX_VISITS = 100_000
MAX_CHUNK_LINES = 120
GRAMMARS = {
    "python": ("tree_sitter_python", "language"),
    "javascript": ("tree_sitter_javascript", "language"),
    "jsx": ("tree_sitter_javascript", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "tsx": ("tree_sitter_typescript", "language_tsx"),
    "go": ("tree_sitter_go", "language"),
    "c": ("tree_sitter_c", "language"),
    "cpp": ("tree_sitter_cpp", "language"),
    "csharp": ("tree_sitter_c_sharp", "language"),
}
TYPE_NODES = frozenset({
    "class_definition", "class_declaration", "interface_declaration", "enum_declaration",
    "struct_specifier", "union_specifier", "enum_specifier", "class_specifier", "type_spec",
    "type_alias_declaration", "record_declaration", "struct_declaration", "delegate_declaration",
})
METHOD_NODES = frozenset({
    "function_definition", "function_declaration", "generator_function_declaration",
    "method_definition", "method_declaration", "constructor_declaration", "destructor_declaration",
    "method_signature", "function_signature", "abstract_method_signature", "local_function_statement",
})
FIELD_NODES = frozenset({
    "field_declaration", "public_field_definition", "property_signature", "property_declaration",
    "field_definition",
})


@dataclass(frozen=True)
class CodeAnalysis:
    symbols: list[JavaSymbol]
    chunks: list[JavaChunk]
    truncated: bool
    has_syntax_errors: bool


@lru_cache(maxsize=len(GRAMMARS))
def _language(name: str) -> Language:
    module_name, factory = GRAMMARS[name]
    return Language(getattr(importlib.import_module(module_name), factory)())


def _text(node: Node | None, raw: bytes) -> str:
    return raw[node.start_byte:node.end_byte].decode("utf-8") if node is not None else ""


def _declarator_name(node: Node | None, raw: bytes) -> tuple[str, bool]:
    """Unwrap C/C++ pointers, references and function declarators, not bodies."""
    function = False
    for _ in range(32):
        if node is None:
            break
        if node.type in {"function_declarator", "pointer_declarator", "reference_declarator", "array_declarator"}:
            # The declarator nearest the name distinguishes a function returning
            # a pointer from a variable/field holding a function pointer.
            function = node.type == "function_declarator"
        if node.type in {"identifier", "field_identifier", "type_identifier", "qualified_identifier",
                         "destructor_name", "operator_name"}:
            return _text(node, raw), function
        next_node = node.child_by_field_name("declarator")
        if next_node is None and node.type == "parenthesized_declarator":
            next_node = next(iter(node.named_children), None)
        node = next_node
    return "", function


def _declarations(node: Node, raw: bytes, language: str) -> list[tuple[str, str]]:
    # A declaration containing parser recovery is not a reliable symbol. Its
    # original text is still partitioned below and errors are explicitly exposed.
    if node.has_error or node.is_missing:
        return []
    name = _text(node.child_by_field_name("name"), raw)
    if node.type in TYPE_NODES:
        return [("type", name)] if name else []
    if node.type in METHOD_NODES:
        if not name:
            name, _ = _declarator_name(node.child_by_field_name("declarator"), raw)
        return [("method", name)] if name else []
    if node.type == "variable_declarator":
        value = node.child_by_field_name("value")
        identifier = node.child_by_field_name("name")
        if identifier is not None and identifier.type == "identifier" and value is not None:
            if value.type in {"arrow_function", "function_expression", "generator_function"}:
                return [("method", name)]
            if value.type in {"class", "class_expression"}:
                return [("type", name)]
    if node.type in FIELD_NODES:
        if node.type == "property_signature" and node.parent is not None:
            if node.parent.type == "object_type" and (
                node.parent.parent is None or node.parent.parent.type != "type_alias_declaration"
            ):
                return []  # anonymous parameter/object shapes are not class fields
        names = node.children_by_field_name("name")
        if not names:
            names = node.children_by_field_name("property")
        if names:
            return [("field", _text(item, raw)) for item in names]
        declarators = node.children_by_field_name("declarator")
        if declarators:
            results = [_declarator_name(item, raw) for item in declarators]
            return [("method" if function else "field", item) for item, function in results if item]
        # C# groups field names inside variable_declaration/variable_declarator.
        result = []
        for child in node.named_children:
            if child.type == "variable_declaration":
                for variable in child.named_children:
                    if variable.type == "variable_declarator":
                        value = _text(variable.child_by_field_name("name"), raw)
                        if value:
                            result.append(("field", value))
        return result
    if language in {"c", "cpp"} and node.type == "declaration":
        # Function prototypes only; local variables are intentionally not fields.
        name, function = _declarator_name(node.child_by_field_name("declarator"), raw)
        return [("method", name)] if name and function else []
    if language == "python" and node.type == "assignment" and node.parent is not None:
        block = node.parent.parent
        if block is not None and block.type == "block" and block.parent is not None \
                and block.parent.type == "class_definition":
            left = node.child_by_field_name("left")
            if left is not None and left.type == "identifier":
                return [("field", _text(left, raw))]
    return []


def analyze_code(content: str, *, source_id: uuid.UUID, language: str) -> CodeAnalysis:
    raw = content.encode("utf-8")
    # A parser belongs to one invocation; only immutable Language objects cache.
    tree = Parser(_language(language)).parse(raw)
    lines = content.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode("utf-8")))
    symbols: list[JavaSymbol] = []
    records: list[tuple[int, int, str, list[str]]] = []
    truncated = False
    visits = 0
    # TreeCursor avoids materializing an unbounded list of a large node's children.
    cursor = tree.walk()
    scopes: list[tuple[int, tuple[str, ...]]] = []
    depth = 0
    while True:
        node = cursor.node
        visits += 1
        if visits > MAX_VISITS:
            truncated = True
            break
        scope = scopes[-1][1] if scopes else ()
        declarations = _declarations(node, raw, language)
        if declarations:
            span = node.parent if node.parent is not None and node.parent.type == "decorated_definition" else node
            start = bisect_right(offsets, span.start_byte)
            end = min(len(lines), bisect_right(offsets, max(span.start_byte, span.end_byte - 1)))
            end = max(start, end)
            for kind, name in declarations:
                symbol_scope = scope
                if language == "go" and node.type == "method_declaration":
                    receiver = node.child_by_field_name("receiver")
                    if receiver is not None:
                        parameter = next((item for item in receiver.named_children
                                          if item.type == "parameter_declaration"), None)
                        receiver_type = parameter.child_by_field_name("type") if parameter is not None else None
                        owner = _text(receiver_type, raw).lstrip("*").strip()
                        if owner:
                            symbol_scope = (*scope, owner)
                qualified = ".".join((*symbol_scope, name))
                symbols.append(JavaSymbol(
                    id=uuid.uuid5(source_id, f"{language}:symbol:{kind}:{qualified}:{start}:{end}"),
                    kind=kind, name=name, qualified_name=qualified,
                    owner=".".join(symbol_scope) or None, start_line=start, end_line=end,
                ))
                records.append((start, end, kind, [*symbol_scope, name]))
                if len(symbols) > MAX_SYMBOLS:
                    truncated = True
                    break
            if truncated:
                break
            # Variables/fields do not introduce lexical scopes.
            if declarations[0][0] in {"type", "method"}:
                scopes.append((depth, (*scope, declarations[0][1])))
        elif node.type in {"namespace_definition", "namespace_declaration"}:
            name = _text(node.child_by_field_name("name"), raw)
            if name:
                scopes.append((depth, (*scope, name)))
        if cursor.goto_first_child():
            depth += 1
            continue
        while True:
            if scopes and scopes[-1][0] == depth:
                scopes.pop()
            if cursor.goto_next_sibling():
                break
            if not cursor.goto_parent():
                return CodeAnalysis(symbols[:MAX_SYMBOLS], _chunks(lines, records, source_id, language),
                                    truncated, tree.root_node.has_error)
            depth -= 1
    return CodeAnalysis(symbols[:MAX_SYMBOLS], _chunks(lines, records[:MAX_SYMBOLS], source_id, language),
                        truncated, tree.root_node.has_error)


def _chunks(lines, records, source_id, language) -> list[JavaChunk]:
    # Partition every original line once, including whitespace and parser errors.
    # Narrowest declaration wins inside a class/function; long spans stay bounded.
    boundaries = {1, len(lines) + 1}
    for start, end, _, _ in records:
        boundaries.update((start, end + 1))
    ordered = sorted(boundaries)
    chunks = []
    for left, right in zip(ordered, ordered[1:]):
        enclosing = [item for item in records if item[0] <= left and item[1] >= right - 1]
        record = min(enclosing, key=lambda item: (item[1] - item[0], -len(item[3]))) if enclosing else None
        kind = ("method" if record[2] == "method" else "type" if record[2] == "type" else "code") if record else "code"
        for start in range(left, right, MAX_CHUNK_LINES):
            end = min(right - 1, start + MAX_CHUNK_LINES - 1)
            text = "".join(lines[start - 1:end])
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            chunks.append(JavaChunk(
                id=uuid.uuid5(source_id, f"{language}:{start}:{end}:{kind}:{digest}"),
                position=len(chunks), kind=kind, heading_path=record[3] if record else [],
                start_line=start, end_line=end, content=text, content_sha256=digest,
            ))
    return chunks


def parse_code(content: str, *, source_id: uuid.UUID, language: str) -> list[JavaChunk]:
    return analyze_code(content, source_id=source_id, language=language).chunks
