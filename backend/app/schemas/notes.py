import uuid
from datetime import datetime
from typing import Annotated, Literal
from pydantic import Field, StringConstraints
from app.schemas.knowledge import StrictModel

Title=Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=120)]
Markdown=Annotated[str,StringConstraints(max_length=60000)]


class NoteCreate(StrictModel):
    request_id:uuid.UUID
    title:Title
    markdown:Markdown=''


class NoteEdit(NoteCreate):
    expected_revision_id:uuid.UUID


class NoteRevisionRead(StrictModel):
    id:uuid.UUID
    note_id:uuid.UUID
    project_id:uuid.UUID
    number:int
    parent_revision_id:uuid.UUID|None
    title:str
    markdown:str
    content_sha256:str
    origin:Literal['human','assistant']
    task_id:uuid.UUID|None
    provenance:dict
    created_at:datetime


class NoteRead(StrictModel):
    id:uuid.UUID
    project_id:uuid.UUID
    current:NoteRevisionRead
    updated_at:datetime


class NoteSummary(StrictModel):
    id:uuid.UUID
    project_id:uuid.UUID
    current_revision_id:uuid.UUID
    title:str
    preview:str
    content_sha256:str
    origin:str
    updated_at:datetime


class NoteList(StrictModel):
    items:list[NoteSummary]
    total:int
    page:int
    page_size:int
    scanned:int=0
    truncated:bool=False


class NoteSnapshot(StrictModel):
    revision_id:uuid.UUID
    source_id:uuid.UUID
    parse_task_id:uuid.UUID
