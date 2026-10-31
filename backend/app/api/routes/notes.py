import uuid
from fastapi import APIRouter, Query
from app.api.dependencies import CurrentUserId, DatabaseSession
from app.core.config import get_settings
from app.schemas.notes import NoteCreate, NoteEdit, NoteRead, NoteRevisionRead, NoteList, NoteSnapshot
from app.services import notes

router=APIRouter(prefix='/projects/{project_id}/notes',tags=['notes'])

@router.get('',response_model=NoteList)
def listing(project_id:uuid.UUID,db:DatabaseSession,user_id:CurrentUserId,page:int=Query(1,ge=1),
            page_size:int=Query(20,ge=1,le=100),query:str|None=Query(None,min_length=1,max_length=200)):
    return notes.listing(db,user_id=user_id,project_id=project_id,page=page,page_size=page_size,query=query)

@router.post('',response_model=NoteRead,status_code=201)
def create(project_id:uuid.UUID,request:NoteCreate,db:DatabaseSession,user_id:CurrentUserId):
    return notes.create(db,user_id=user_id,project_id=project_id,request=request)

@router.get('/revisions/{revision_id}',response_model=NoteRevisionRead)
def revision(project_id:uuid.UUID,revision_id:uuid.UUID,db:DatabaseSession,user_id:CurrentUserId):
    return notes.revision(db,user_id=user_id,project_id=project_id,revision_id=revision_id)

@router.post('/revisions/{revision_id}/source',response_model=NoteSnapshot)
def snapshot(project_id:uuid.UUID,revision_id:uuid.UUID,db:DatabaseSession,user_id:CurrentUserId):
    return notes.snapshot(db,user_id=user_id,project_id=project_id,revision_id=revision_id,settings=get_settings())

@router.get('/{note_id}',response_model=NoteRead)
def read(project_id:uuid.UUID,note_id:uuid.UUID,db:DatabaseSession,user_id:CurrentUserId):
    return notes.read(db,user_id=user_id,project_id=project_id,note_id=note_id)

@router.put('/{note_id}',response_model=NoteRevisionRead)
def edit(project_id:uuid.UUID,note_id:uuid.UUID,request:NoteEdit,db:DatabaseSession,user_id:CurrentUserId):
    return notes.edit(db,user_id=user_id,project_id=project_id,note_id=note_id,request=request)

@router.get('/{note_id}/revisions',response_model=list[NoteRevisionRead])
def history(project_id:uuid.UUID,note_id:uuid.UUID,db:DatabaseSession,user_id:CurrentUserId,
            page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):
    return notes.history(db,user_id=user_id,project_id=project_id,note_id=note_id,page=page,page_size=page_size)
