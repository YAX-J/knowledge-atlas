import { apiRequest } from './client'
import type { ApiProject, ApiProjectList } from './knowledgeAtlas'

export interface AnswerFeedback { id:string;turn_id:string;claim_index:number;claim_text:string;category:string;comment:string;answer_sha256:string;created_at:string }
export interface FeedbackInput { request_id:string;claim_index:number;category:string;comment:string }
export const editProject=(project:ApiProject,name:string,description:string)=>apiRequest<ApiProject>(`/projects/${project.id}`,{method:'PUT',body:JSON.stringify({name,description,expected_updated_at:project.updated_at})})
export const archiveProject=(project:ApiProject,archived:boolean)=>apiRequest<ApiProject>(`/projects/${project.id}/archive`,{method:'PUT',body:JSON.stringify({archived,expected_updated_at:project.updated_at})})
export const archivedProjects=(page=1)=>apiRequest<ApiProjectList>(`/projects?archived=true&page=${page}&page_size=20`)
export const archiveSource=(project:string,source:string,archived:boolean,reason:string)=>apiRequest<{source_id:string;archived:boolean}>(`/projects/${project}/sources/${source}/archive`,{method:'PUT',body:JSON.stringify({archived,reason})})
export const listFeedback=(project:string,turn:string)=>apiRequest<AnswerFeedback[]>(`/projects/${project}/answers/${turn}/feedback`)
export const saveFeedback=(project:string,turn:string,input:FeedbackInput)=>apiRequest<AnswerFeedback>(`/projects/${project}/answers/${turn}/feedback`,{method:'POST',body:JSON.stringify(input)})
