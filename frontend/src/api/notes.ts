import { apiRequest } from './client'
import type { Page } from '../types'
export interface NoteRevision {id:string;note_id:string;project_id:string;number:number;parent_revision_id:string|null;title:string;markdown:string;content_sha256:string;origin:'human'|'assistant';task_id:string|null;provenance:Record<string,unknown>;created_at:string}
export interface Note {id:string;project_id:string;current:NoteRevision;updated_at:string}
export interface NoteSummary {id:string;current_revision_id:string;title:string;preview:string;content_sha256:string;origin:'human'|'assistant'}
export interface NoteEdit {request_id:string;expected_revision_id:string;title:string;markdown:string}
const path=(project:string)=>`/projects/${project}/notes`
export const listNotes=(project:string,page=1,query='')=>apiRequest<Page<NoteSummary>&{truncated:boolean}>(`${path(project)}?page=${page}&page_size=20${query?`&query=${encodeURIComponent(query)}`:''}`)
export const getNote=(project:string,id:string)=>apiRequest<Note>(`${path(project)}/${id}`)
export const getNoteRevision=(project:string,id:string)=>apiRequest<NoteRevision>(`${path(project)}/revisions/${id}`)
export const getNoteHistory=(project:string,id:string,page=1)=>apiRequest<NoteRevision[]>(`${path(project)}/${id}/revisions?page=${page}`)
export const createNote=(project:string,input:{request_id:string;title:string;markdown:string})=>apiRequest<Note>(path(project),{method:'POST',body:JSON.stringify(input)})
export const editNote=(project:string,id:string,input:NoteEdit)=>apiRequest<NoteRevision>(`${path(project)}/${id}`,{method:'PUT',body:JSON.stringify(input)})
export const snapshotNote=(project:string,revision:string)=>apiRequest<{source_id:string;parse_task_id:string}>(`${path(project)}/revisions/${revision}/source`,{method:'POST'})
