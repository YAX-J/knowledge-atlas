"""Versioned read-only assistant contracts, separate from evidence questions."""
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, RootModel, StringConstraints, model_validator

from app.schemas.knowledge import StrictModel
from app.workflows.contracts import RunEvent

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class AssistantRequest(StrictModel):
    protocol: Literal['assistant-task-v1', 'assistant-task-v2', 'assistant-task-v3'] = 'assistant-task-v1'
    request_id: uuid.UUID
    goal: Text
    source_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    snapshot_id: uuid.UUID | None = None
    valid_at: AwareDatetime | None = None
    model_limit: int = Field(default=8, ge=0, le=8, strict=True)
    tool_limit: int = Field(default=16, ge=0, le=16, strict=True)
    note_revision_ids: list[uuid.UUID] = Field(default_factory=list,max_length=20)
    allowed_actions: list[Literal['create_note_draft','propose_note_revision','import_repository_snapshot',
        'request_source_parse','propose_knowledge','propose_knowledge_change','create_report_draft']] = Field(default_factory=list,max_length=7)
    repository_id: uuid.UUID | None = None
    repository_commit: Annotated[str,StringConstraints(pattern=r'^[0-9a-f]{40}$')] | None = None
    whole_repository: bool = False
    repository_ref: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255, pattern=r'^[^\x00\r\n]+$')] | None = None

    def request_data(self):
        exclude={'request_id'}
        if self.protocol!='assistant-task-v3':
            exclude|={'note_revision_ids','allowed_actions','repository_id','repository_commit'}
        if not self.whole_repository:
            exclude |= {'whole_repository', 'repository_ref'}
        return self.model_dump(mode='json',exclude=exclude)

    @model_validator(mode='after')
    def scope_shape(self):
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError('Duplicate source IDs')
        if self.snapshot_id and not self.source_ids:
            raise ValueError('A snapshot requires explicit source versions')
        if self.valid_at and self.source_ids:
            raise ValueError('Historical knowledge cannot mix current source material')
        if len(set(self.note_revision_ids))!=len(self.note_revision_ids) or len(set(self.allowed_actions))!=len(self.allowed_actions):
            raise ValueError('Duplicate note revisions or actions')
        if self.protocol!='assistant-task-v3' and (self.note_revision_ids or self.allowed_actions or self.repository_id or self.repository_commit):
            raise ValueError('Workflow capabilities require v3')
        if self.valid_at and (self.note_revision_ids or self.allowed_actions):
            raise ValueError('Historical knowledge cannot mix notes or writes')
        if self.whole_repository:
            if (self.protocol != 'assistant-task-v3' or self.repository_id is None or
                    'import_repository_snapshot' not in self.allowed_actions or self.source_ids or self.snapshot_id or
                    (self.repository_ref and self.repository_commit)):
                raise ValueError('Whole repository requires an authorized repository, one ref or commit, and no selected sources')
            return self
        if self.repository_ref is not None:
            raise ValueError('A repository ref requires whole repository mode')
        if ('import_repository_snapshot' in self.allowed_actions)!=(self.repository_id is not None and self.repository_commit is not None):
            raise ValueError('Import authorization requires an exact repository and commit')
        if (self.repository_id is None)!=(self.repository_commit is None):raise ValueError('Incomplete repository selection')
        return self


class ReportClaim(StrictModel):
    text: Text
    status: Literal['referenced', 'uncertain']
    reference_ids: list[uuid.UUID] = Field(max_length=8)

    @model_validator(mode='after')
    def references_required(self):
        if self.status == 'referenced' and not self.reference_ids:
            raise ValueError('Referenced conclusions require references')
        if len(set(self.reference_ids)) != len(self.reference_ids):
            raise ValueError('Duplicate references')
        return self


class ReportDraft(StrictModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    claims: list[ReportClaim] = Field(min_length=1, max_length=12)
    missing_information: list[Text] = Field(max_length=8)

    @model_validator(mode='after')
    def uncertainty(self):
        if any(claim.status == 'uncertain' for claim in self.claims) and not self.missing_information:
            raise ValueError('Uncertainty requires missing information')
        return self


class FinishAction(StrictModel):
    action: Literal['finish']
    report: ReportDraft


class AskAction(StrictModel):
    action: Literal['ask_user']
    question: Text


class AssistantDecision(RootModel[Annotated[FinishAction | AskAction, Field(discriminator='action')]]):
    pass


class AssistantReference(StrictModel):
    id: uuid.UUID
    kind: Literal['source', 'code', 'knowledge', 'note']
    source_id: uuid.UUID | None = None
    note_id: uuid.UUID | None = None
    revision_id: uuid.UUID | None = None
    chunk_id: uuid.UUID | None = None
    evidence_id: uuid.UUID | None = None
    source_sha256: Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
    path: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    start_line: int = Field(ge=1, strict=True)
    end_line: int = Field(ge=1, strict=True)
    quote: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    snapshot_id: uuid.UUID | None = None
    commit_sha: str | None = None

    @model_validator(mode='after')
    def provenance(self):
        if self.kind=='note':
            if not self.note_id or not self.revision_id or self.source_id or self.chunk_id or self.evidence_id or self.snapshot_id or self.commit_sha:
                raise ValueError('Notes require exact immutable revision provenance only')
        elif self.source_id is None or self.note_id or self.revision_id:
            raise ValueError('Source references require their exact source')
        if self.end_line < self.start_line:
            raise ValueError('Invalid exact line range')
        if (self.kind == 'knowledge') != (self.evidence_id is not None):
            raise ValueError('Only formal knowledge references have evidence IDs')
        if self.kind == 'knowledge' and self.chunk_id is None:
            raise ValueError('Formal evidence requires its exact chunk')
        if (self.snapshot_id is None) != (self.commit_sha is None):
            raise ValueError('Commit references require both snapshot and commit')
        return self


class AssistantResult(StrictModel):
    protocol: Literal['assistant-report-v1','assistant-report-v2'] = 'assistant-report-v1'
    action: Literal['finish', 'ask_user']
    report: ReportDraft | None = None
    question: Text | None = None
    references: list[AssistantReference] = Field(default_factory=list)


class AssistantSummary(StrictModel):
    id: uuid.UUID
    project_id: uuid.UUID
    goal: str
    status: Literal['queued', 'running', 'waiting_approval', 'succeeded', 'failed', 'interrupted', 'cancelled']
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class AssistantRead(AssistantSummary):
    scope: dict
    result: AssistantResult | None
    events: list[RunEvent]
    usage: dict
    execution_mode: Literal['sync_v1','async_v2','async_v3'] = 'sync_v1'
    revision: int = 0
    checkpoint_id: uuid.UUID | None = None
    unknown_model_attempts: int = 0
    can_continue: bool = False
    artifact_ids: list[uuid.UUID] = Field(default_factory=list)
    final_artifact_id: uuid.UUID | None = None
    operations: list[dict] = Field(default_factory=list)
    unknown_operations: int = 0
    remaining: dict = Field(default_factory=dict)


class AssistantContinue(StrictModel):
    request_id: uuid.UUID
    expected_revision: int = Field(ge=0, strict=True)
    checkpoint_id: uuid.UUID | None = None
    acknowledge_unknown: bool = False


class AssistantEvents(StrictModel):
    items: list[RunEvent]
    next_sequence: int
    has_more: bool


class AssistantList(StrictModel):
    items: list[AssistantSummary]
    total: int
    page: int
    page_size: int
