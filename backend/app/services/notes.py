"""Scoped editable notes. Revisions and citation provenance are append-only."""
import hashlib
import uuid
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.errors import AppError
from app.models.domain import Project, utc_now
from app.models.notes import Note, NoteRevision, NoteSource
from app.schemas.notes import NoteRead, NoteRevisionRead, NoteSummary, NoteList, NoteSnapshot
from app.services.projects import get_project


def fail(code='NOTE_NOT_FOUND', message='笔记或修订不属于当前项目', status=404):
    raise AppError(status_code=status,code=code,message=message)


def lock_project(db,user_id,project_id):
    get_project(db,user_id=user_id,project_id=project_id)
    db.execute(select(Project.id).where(Project.id==project_id,Project.user_id==user_id).with_for_update())


def revision(db,*,user_id,project_id,revision_id):
    get_project(db,user_id=user_id,project_id=project_id)
    item=db.scalar(select(NoteRevision).where(NoteRevision.id==revision_id,NoteRevision.user_id==user_id,
        NoteRevision.project_id==project_id))
    if item is None:fail()
    return NoteRevisionRead.model_validate(item,from_attributes=True)


def read(db,*,user_id,project_id,note_id):
    get_project(db,user_id=user_id,project_id=project_id)
    note=db.scalar(select(Note).where(Note.id==note_id,Note.user_id==user_id,Note.project_id==project_id)
        .execution_options(populate_existing=True))
    if note is None:fail()
    return NoteRead(id=note.id,project_id=project_id,updated_at=note.updated_at,
        current=revision(db,user_id=user_id,project_id=project_id,revision_id=note.current_revision_id))


def create(db,*,user_id,project_id,request,origin='human',task_id=None,provenance=None,commit=True):
    lock_project(db,user_id,project_id)
    note=db.get(Note,request.request_id)
    rid=uuid.uuid5(request.request_id,'revision:1')
    if note:
        if (note.user_id,note.project_id)!=(user_id,project_id):fail()
        first=revision(db,user_id=user_id,project_id=project_id,revision_id=rid)
        if (first.title,first.markdown,first.origin,first.task_id,first.provenance)!=(request.title,request.markdown,origin,task_id,provenance or {}):
            fail('NOTE_REQUEST_CONFLICT','笔记标识已绑定其他输入',409)
    else:
        note=Note(id=request.request_id,user_id=user_id,project_id=project_id)
        db.add(note);db.flush()
        _append(db,note,rid,request.title,request.markdown,1,None,origin,task_id,provenance or {})
    if commit:db.commit()
    else:db.flush()
    return read(db,user_id=user_id,project_id=project_id,note_id=note.id)


def _append(db,note,rid,title,markdown,number,parent,origin,task_id,provenance):
    digest=hashlib.sha256((title+'\n'+markdown).encode()).hexdigest()
    db.add(NoteRevision(id=rid,note_id=note.id,user_id=note.user_id,project_id=note.project_id,number=number,
        parent_revision_id=parent,title=title,markdown=markdown,content_sha256=digest,origin=origin,
        task_id=task_id,provenance=provenance))
    note.current_revision_id=rid;note.updated_at=utc_now()


def edit(db,*,user_id,project_id,note_id,request,origin='human',task_id=None,provenance=None,commit=True):
    lock_project(db,user_id,project_id)
    current=read(db,user_id=user_id,project_id=project_id,note_id=note_id).current
    parent=revision(db,user_id=user_id,project_id=project_id,revision_id=request.expected_revision_id)
    if parent.note_id!=note_id:fail()
    actual_provenance=provenance if provenance is not None else parent.provenance
    prior=db.get(NoteRevision,request.request_id)
    if prior:
        if (prior.note_id,prior.user_id,prior.project_id)!=(note_id,user_id,project_id):fail()
        if (prior.parent_revision_id,prior.title,prior.markdown,prior.origin,prior.task_id,prior.provenance)!=(
            request.expected_revision_id,request.title,request.markdown,origin,task_id,actual_provenance):
            fail('NOTE_REQUEST_CONFLICT','修订标识已绑定其他输入',409)
    else:
        if current.id!=request.expected_revision_id:fail('NOTE_REVISION_CONFLICT','笔记已有新修订；已保留本地草稿，请先刷新比对',409)
        _append(db,db.get(Note,note_id),request.request_id,request.title,request.markdown,current.number+1,
            current.id,origin,task_id,actual_provenance)
    if commit:db.commit()
    else:db.flush()
    return revision(db,user_id=user_id,project_id=project_id,revision_id=request.request_id)


def listing(db,*,user_id,project_id,page=1,page_size=20,query=None):
    get_project(db,user_id=user_id,project_id=project_id)
    filters=(Note.user_id==user_id,Note.project_id==project_id)
    total=db.scalar(select(func.count()).select_from(Note).where(*filters)) or 0
    rows=list(db.execute(select(Note,NoteRevision).join(NoteRevision,Note.current_revision_id==NoteRevision.id)
        .where(*filters).order_by(Note.updated_at.desc(),Note.id).limit(101 if query else page_size)
        .offset(0 if query else (page-1)*page_size)))
    scanned=0;chars=0;found=[];truncated=bool(query and len(rows)>100)
    for note,rev in rows[:100] if query else rows:
        chars+=len(rev.markdown)+len(rev.title)
        if query and chars>200000:truncated=True;break
        scanned+=1
        if query and query.casefold() not in (rev.title+'\n'+rev.markdown).casefold():continue
        found.append(NoteSummary(id=note.id,project_id=project_id,current_revision_id=rev.id,title=rev.title,
            preview=rev.markdown[:160],content_sha256=rev.content_sha256,origin=rev.origin,updated_at=note.updated_at))
    if query:total=len(found);found=found[(page-1)*page_size:page*page_size]
    return NoteList(items=found,total=total,page=page,page_size=page_size,scanned=scanned,truncated=truncated)


def history(db,*,user_id,project_id,note_id,page=1,page_size=20):
    read(db,user_id=user_id,project_id=project_id,note_id=note_id)
    return [NoteRevisionRead.model_validate(r,from_attributes=True) for r in db.scalars(select(NoteRevision)
        .where(NoteRevision.note_id==note_id,NoteRevision.user_id==user_id,NoteRevision.project_id==project_id)
        .order_by(NoteRevision.number.desc()).offset((page-1)*page_size).limit(page_size))]


def snapshot(db,*,user_id,project_id,revision_id,settings,commit=True):
    lock_project(db,user_id,project_id)
    rev=revision(db,user_id=user_id,project_id=project_id,revision_id=revision_id)
    mapping=db.get(NoteSource,revision_id)
    if mapping is None:
        from app.services.ingestion import create_source_and_task_from_bytes
        with Session(bind=db.connection(),expire_on_commit=False,join_transaction_mode='create_savepoint') as nested:
            source,task,_=create_source_and_task_from_bytes(nested,settings=settings,user_id=user_id,project_id=project_id,
                filename=f'note-{rev.note_id}-{rev.number}.md',raw_content=('# '+rev.title+'\n\n'+rev.markdown).encode(),
                source_type='markdown',relative_path=None,repository_id=None)
        mapping=NoteSource(revision_id=revision_id,user_id=user_id,project_id=project_id,source_id=source.id,parse_task_id=task.id)
        db.add(mapping)
    if commit:db.commit()
    else:db.flush()
    return NoteSnapshot(revision_id=revision_id,source_id=mapping.source_id,parse_task_id=mapping.parse_task_id)
