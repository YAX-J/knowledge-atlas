import uuid
from datetime import datetime
from typing import Annotated, Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_serializer, model_validator


class WorkflowRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id: uuid.UUID
    kind: Literal['knowledge_pipeline','question_pipeline']
    source_id: uuid.UUID|None=None
    note_revision_id: uuid.UUID | None = None
    snapshot_id: uuid.UUID|None=None
    version_ids: list[uuid.UUID]=Field(default_factory=list,max_length=99)
    code_strategy: Literal['single_step','tools','semantic']='single_step'
    include_code_analysis: bool=False
    question: Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=200)]|None=None
    valid_at: AwareDatetime|None=None
    retrieval_mode: Literal['bm25','bm25_source','rrf','hybrid','vector']='bm25'
    model_limit: int=Field(default=8,ge=0,le=8,strict=True)
    tool_limit: int=Field(default=16,ge=0,le=16,strict=True)
    embedding_limit: int=Field(default=4,ge=0,le=4,strict=True)

    @model_validator(mode='after')
    def task_shape(self):
        if self.kind=='knowledge_pipeline' and ((self.source_id is None) == (self.note_revision_id is None) or self.question is not None or self.valid_at is not None):
            raise ValueError('Knowledge workflow requires exactly one source or note revision and no question/history time')
        if self.note_revision_id and self.kind != 'knowledge_pipeline':
            raise ValueError('A note revision is only supported for knowledge extraction')
        if self.kind=='question_pipeline' and not self.question:raise ValueError('Question required')
        if self.include_code_analysis and not self.source_id:raise ValueError('Code analysis requires a source')
        if self.valid_at and self.include_code_analysis:raise ValueError('Historical questions use confirmed historical evidence without current-code hints')
        if self.snapshot_id and self.version_ids:raise ValueError('Cannot mix snapshot and local versions')
        if len(set(self.version_ids))!=len(self.version_ids):raise ValueError('Duplicate version IDs')
        if not self.source_id and (self.snapshot_id or self.version_ids):raise ValueError('Code context requires a source')
        if (self.snapshot_id or self.version_ids) and not self.include_code_analysis:raise ValueError('Code selection requires code analysis')
        return self


class RunEvent(BaseModel):
    sequence: int
    agent: str
    kind: str
    status: str
    elapsed_ms: float
    attempt: int|None=None
    tool_name: str|None=None


class WorkflowScopeRead(BaseModel):
    note_revision_id: uuid.UUID | None = None
    retrieval_mode: Literal['bm25','bm25_source','rrf','hybrid','vector']|None=None
    valid_at: AwareDatetime|None=None
    include_code_analysis: bool=False
    code_strategy: Literal['single_step','tools','semantic']|None=None
    snapshot_id: uuid.UUID|None=None
    version_ids: list[uuid.UUID]=Field(default_factory=list)

    @model_serializer(mode='wrap')
    def serialize_scope(self, handler):
        fields = handler(self)
        if self.note_revision_id is None:
            fields.pop('note_revision_id', None)
        return fields


class WorkflowRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    source_id: uuid.UUID|None
    kind: str
    status: Literal['running','awaiting_review','succeeded','failed','interrupted']
    result: dict|None
    events: list[RunEvent]
    usage: dict
    error_code: str|None
    created_at: datetime
    updated_at: datetime
    review_counts: dict[str,int]=Field(default_factory=dict)
    scope: WorkflowScopeRead|None=None


class WorkflowList(BaseModel):
    items: list[WorkflowRead]
    total: int
    page: int
    page_size: int


class WorkflowSummary(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    source_id: uuid.UUID|None
    kind: str
    status: Literal['running','awaiting_review','succeeded','failed','interrupted']
    error_code: str|None
    created_at: datetime
    updated_at: datetime


class WorkflowSummaryList(BaseModel):
    items: list[WorkflowSummary]
    total: int
    page: int
    page_size: int
