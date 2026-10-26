import { apiRequest } from './client'
import type { Conversation, ConversationTurn, IdentityInfo, KnowledgeOperation, OperationInput, Page, ProjectOverview, QuestionRetrievalMode } from '../types'

export const getOverview = (project: string) => apiRequest<ProjectOverview>(`/projects/${project}/overview`)
export const getIdentity = (project: string, entity: string, validAt = '') => apiRequest<IdentityInfo>(
  `/projects/${project}/knowledge/entities/${entity}/identity${validAt ? `?${new URLSearchParams({ valid_at: validAt })}` : ''}`)
export const operateKnowledge = (project: string, input: OperationInput & { request_id: string }) =>
  apiRequest<KnowledgeOperation>(`/projects/${project}/knowledge-operations`, { method: 'POST', body: JSON.stringify(input) })
export const listOperations = (project: string, page = 1) => apiRequest<Page<KnowledgeOperation>>(`/projects/${project}/knowledge-operations?page=${page}&page_size=20`)
export const proposeEvolutionGroup = (project: string, input: { request_id: string; old_entity_ids: string[]; new_entity_ids: string[]; reason: string }) =>
  apiRequest<KnowledgeOperation>(`/projects/${project}/knowledge-change-groups`, { method: 'POST', body: JSON.stringify(input) })
export const createConversation = (project: string, title = '新的证据会话') =>
  apiRequest<Conversation>(`/projects/${project}/conversations`, { method: 'POST', body: JSON.stringify({ title }) })
export const listConversations = (project: string, page = 1) => apiRequest<Page<Conversation>>(`/projects/${project}/conversations?page=${page}&page_size=20`)
export const listConversationTurns = (project: string, conversation: string, page = 1) =>
  apiRequest<Page<ConversationTurn>>(`/projects/${project}/conversations/${conversation}/turns?page=${page}&page_size=20`)
export const askConversation = (project: string, conversation: string, input: { request_id: string; question: string; retrieval_mode: QuestionRetrievalMode; retry_interrupted?: boolean }) =>
  apiRequest<ConversationTurn>(`/projects/${project}/conversations/${conversation}/turns`, {
    method: 'POST', body: JSON.stringify(input), signal: AbortSignal.timeout(420_000),
  })
