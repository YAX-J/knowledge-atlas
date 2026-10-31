"""Strict arguments shared by tool contracts and human approval endpoints."""
import uuid
from typing import Literal
from pydantic import Field
from app.schemas.knowledge import StrictModel
from app.schemas.notes import Title, Markdown
from app.schemas.assistant import ReportDraft, Text
from app.schemas.evolution import ChangeCreate

class Empty(StrictModel):pass
class NoteRange(StrictModel):
    revision_id:uuid.UUID
    start_line:int=Field(default=1,ge=1,strict=True)
    end_line:int=Field(ge=1,strict=True)
class NoteDraft(StrictModel):
    title:Title
    markdown:Markdown
class NoteProposal(NoteDraft):
    note_id:uuid.UUID
    expected_revision_id:uuid.UUID
class SourceArgs(StrictModel):source_id:uuid.UUID
class NoteSourceArgs(StrictModel):revision_id:uuid.UUID
class EvidenceArgs(StrictModel):evidence_id:uuid.UUID
class ChangeArgs(StrictModel):
    action:Literal['merge','retire','supersede','confirm_candidates']
    reason:Text
    knowledge_id:uuid.UUID|None=None
    target_id:uuid.UUID|None=None
    kind:Literal['entity','relationship']='entity'
    category:Literal['correction','obsolete']='obsolete'
    change:ChangeCreate|None=None
    candidate_ids:list[uuid.UUID]=Field(default_factory=list,max_length=30)
    def checked(self):
        if self.action=='confirm_candidates':
            return bool(self.candidate_ids) and len(set(self.candidate_ids))==len(self.candidate_ids) and not(self.knowledge_id or self.target_id or self.change)
        if self.candidate_ids:return False
        if self.action=='supersede':
            return self.change is not None and self.change.kind=='SUPERSEDES' and not(self.knowledge_id or self.target_id)
        if self.change:return False
        return self.knowledge_id is not None and ((self.action=='merge' and self.target_id is not None and self.kind=='entity') or (self.action=='retire' and self.target_id is None))
class ReportArgs(StrictModel):report:ReportDraft
class ApprovalRequest(StrictModel):
    request_id:uuid.UUID
    operation_id:uuid.UUID
    proposal_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    decision:Literal['approve','reject']
class SaveArtifact(StrictModel):request_id:uuid.UUID
