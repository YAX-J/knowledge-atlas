"""Shared derived syntax records; no parsers, persistence or formal graph writes."""
import uuid
from dataclasses import dataclass


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
class CodeAnalysis:
    symbols: list[JavaSymbol]
    chunks: list[JavaChunk]
    call_sites: list["CodeCallSite"]
    truncated: bool
    has_syntax_errors: bool


@dataclass(frozen=True)
class CodeCallSite:
    id: uuid.UUID
    caller_id: uuid.UUID | None
    expression: str
    receiver: str | None
    callee_name: str
    line: int
    column: int
    quote: str
