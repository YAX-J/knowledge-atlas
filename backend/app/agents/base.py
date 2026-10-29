"""Small shared contracts; agents never receive database sessions."""
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class SourceFile:
    id: UUID
    relative_path: str
    original_name: str
    content: str
    source_type: str
    size_bytes: int


class Agent(Protocol):
    name: str
    def run(self, task: Any, context: Any) -> Any: ...
