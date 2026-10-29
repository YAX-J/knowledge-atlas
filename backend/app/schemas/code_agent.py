import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalysisSnapshotChoice(BaseModel):
    id: uuid.UUID
    commit_sha: str
    ref: str
    truncated: bool


class AnalysisVersionChoice(BaseModel):
    id: uuid.UUID
    created_at: datetime
    size_bytes: int


class AnalysisVersionGroup(BaseModel):
    path: str
    versions: list[AnalysisVersionChoice]
    truncated: bool


class CodeAnalysisContextsRead(BaseModel):
    default_snapshot_id: uuid.UUID | None
    snapshots: list[AnalysisSnapshotChoice]
    version_groups: list[AnalysisVersionGroup]
    truncated: bool


class AgentCallDecisionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    call_id: uuid.UUID
    target_ids: list[uuid.UUID] = Field(max_length=20)
    resolution: Literal["resolved", "ambiguous", "unresolved"]
    confidence: float = Field(ge=0, le=1)
    resolution_basis: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def target_count_matches_resolution(self):
        count = len(set(self.target_ids))
        if len(self.target_ids) != count:
            raise ValueError("target_ids must be unique")
        if self.resolution == "resolved" and count != 1:
            raise ValueError("resolved decisions require exactly one target")
        if self.resolution == "ambiguous" and count < 2:
            raise ValueError("ambiguous decisions require at least two targets")
        if self.resolution == "unresolved" and count:
            raise ValueError("unresolved decisions cannot contain targets")
        return self


class AgentCallAnalysisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decisions: list[AgentCallDecisionDraft] = Field(max_length=200)


class AgentRelatedSymbolRead(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_path: str
    language: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    quote: str


class AgentCrossFileCallRead(BaseModel):
    id: uuid.UUID
    caller_id: uuid.UUID | None
    target_ids: list[uuid.UUID]
    receiver: str | None
    callee_name: str
    line: int
    column: int
    call_quote: str
    resolution: Literal["resolved", "ambiguous", "unresolved"]
    confidence: float
    resolution_basis: str


class AgentCallAnalysisRead(BaseModel):
    context: dict = Field(default_factory=dict)
    source_id: uuid.UUID
    language: str
    model: str | None
    prompt_version: str
    calls: list[AgentCrossFileCallRead]
    related_symbols: list[AgentRelatedSymbolRead]
    scanned_source_count: int
    detected_call_count: int
    candidate_call_count: int
    provider_call_count: int
    truncated: bool
    has_syntax_errors: bool
    strategy: Literal["single_step", "tools", "semantic"] = "single_step"
    tool_call_count: int = 0
    tool_trace: list[dict] = Field(default_factory=list)
    candidate_generation: str = 'syntax'
    uncovered_call_count: int = 0
    semantic_diagnostics: list[dict] = Field(default_factory=list)
