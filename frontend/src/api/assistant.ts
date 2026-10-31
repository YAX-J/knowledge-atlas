import { apiRequest } from './client'
import type { AgentEvent } from './agents'
import type { Page } from '../types'

export interface AssistantInput {
  request_id: string
  protocol?: 'assistant-task-v1' | 'assistant-task-v2'
  goal: string
  source_ids: string[]
  snapshot_id?: string
  valid_at?: string
  model_limit?: number
  tool_limit?: number
}
export interface AssistantReference {
  id: string; kind: 'source' | 'code' | 'knowledge'; source_id: string; chunk_id: string | null
  evidence_id: string | null; source_sha256: string; path: string; start_line: number; end_line: number
  quote: string; snapshot_id: string | null; commit_sha: string | null
}
export interface AssistantSummary {
  id: string; project_id: string; goal: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'interrupted' | 'cancelled'
  error_code: string | null; created_at: string; updated_at: string
}
export interface AssistantTask extends AssistantSummary {
  execution_mode?: 'sync_v1' | 'async_v2'
  revision?: number
  checkpoint_id?: string | null
  unknown_model_attempts?: number
  can_continue?: boolean
  artifact_ids?: string[]
  scope: {source_ids: string[]; snapshot_id: string | null; commit_sha: string | null; valid_at: string | null}
  result: {
    protocol: 'assistant-report-v1'; action: 'finish' | 'ask_user'; question: string | null
    report: {title: string; claims: {text: string; status: 'referenced' | 'uncertain'; reference_ids: string[]}[]; missing_information: string[]} | null
    references: AssistantReference[]
  } | null
  events: AgentEvent[]
  usage: {model?: number; tool?: number; embedding?: number; limits?: {model: number; tool: number; embedding: number}}
}
export interface AssistantContinue {request_id: string; expected_revision: number; checkpoint_id: string | null; acknowledge_unknown: boolean}
const path = (project: string) => `/projects/${project}/assistant/tasks`
export const listAssistantTasks = (project: string, page = 1) => apiRequest<Page<AssistantSummary>>(`${path(project)}?page=${page}&page_size=10`)
export const getAssistantTask = (project: string, id: string) => apiRequest<AssistantTask>(`${path(project)}/${id}`)
export const startAssistantTask = (project: string, input: AssistantInput) => apiRequest<AssistantTask>(path(project), {
  method: 'POST', body: JSON.stringify(input), signal: AbortSignal.timeout(260000),
})
export const cancelAssistantTask = (project: string, id: string) => apiRequest<AssistantTask>(`${path(project)}/${id}/cancel`, {method: 'POST'})
export const continueAssistantTask = (project: string, id: string, input: AssistantContinue) => apiRequest<AssistantTask>(`${path(project)}/${id}/continue`, {method: 'POST', body: JSON.stringify(input)})
