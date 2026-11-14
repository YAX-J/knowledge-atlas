import { apiRequest } from './client'
import type { Page, QuestionAnswer } from '../types'
import type { AgentCallAnalysis } from './knowledgeAtlas'

export interface AgentEvent { sequence:number; agent:string; kind:string; status:string; elapsed_ms:number; attempt?:number|null; tool_name?:string|null }
export interface WorkflowInput {
  request_id:string; kind:'knowledge_pipeline'|'question_pipeline'; source_id?:string; note_revision_id?:string
  question?:string; retrieval_mode?:'bm25'|'bm25_source'|'rrf'|'hybrid'|'vector'
  valid_at?:string; snapshot_id?:string; version_ids?:string[]
  include_code_analysis?:boolean; code_strategy?:'single_step'|'tools'|'semantic'
  model_limit?:number; tool_limit?:number; embedding_limit?:number
}
export interface AgentRunSummary {
  id:string; project_id:string; source_id:string|null; kind:string
  status:'running'|'awaiting_review'|'succeeded'|'failed'|'interrupted'
  error_code:string|null;created_at:string;updated_at:string
}
export interface AgentRun extends AgentRunSummary {
  result:{candidate_ids?:string[];extraction_task_id?:string;answer?:QuestionAnswer;code_analysis?:AgentCallAnalysis|null}|null
  events:AgentEvent[]; usage:{model?:number;tool?:number;embedding?:number}; error_code:string|null
  created_at:string;updated_at:string;review_counts:Record<string,number>
  scope?: {retrieval_mode:'bm25'|'bm25_source'|'rrf'|'hybrid'|'vector'|null;valid_at:string|null;
    include_code_analysis:boolean;code_strategy:'single_step'|'tools'|'semantic'|null;
    snapshot_id:string|null;version_ids:string[];note_revision_id?:string|null} | null
}
export const listAgentRuns=(project:string,page=1)=>apiRequest<Page<AgentRunSummary>>(`/projects/${project}/agent-runs?page=${page}&page_size=10&summary=true`)
export const getAgentRun=(project:string,id:string)=>apiRequest<AgentRun>(`/projects/${project}/agent-runs/${id}`)
export const startAgentRun=(project:string,input:WorkflowInput)=>apiRequest<AgentRun>(`/projects/${project}/agent-runs`,{
  method:'POST',body:JSON.stringify(input),signal:AbortSignal.timeout(1000*900) })
export const resumeAgentRun=(project:string,id:string)=>apiRequest<AgentRun>(`/projects/${project}/agent-runs/${id}/resume`,{method:'POST'})
