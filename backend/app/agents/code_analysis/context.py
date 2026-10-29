from dataclasses import dataclass
from app.agents.base import SourceFile
from app.core.config import Settings


@dataclass(frozen=True)
class CodeContext:
    source: SourceFile
    related: tuple[SourceFile,...]
    settings: Settings
    truncated: bool
    selection: dict


@dataclass(frozen=True)
class CodeTask:
    strategy: str='single_step'
