import { apiRequest } from './client'
import type { EmbeddingRebuildResult, EntityDetail, KnowledgeCandidate, KnowledgeSearchMode, KnowledgeSearchResult, ProjectGraphData, QuestionAnswer, RelationshipDetail, ReviewDecision } from '../types'

export interface ApiProject {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
}

export interface ApiProjectList {
  items: ApiProject[]
  page: number
  page_size: number
  total: number
}

export interface SourceUploadResult {
  source_id: string
  task_id: string
  status: ProcessingTask['status']
}

export interface ApiSource {
  id: string
  project_id: string
  original_name: string
  media_type: string
  source_type: string
  size_bytes: number
  content_sha256: string
  status: 'uploaded' | 'processing' | 'ready' | 'failed'
  content_preview: string
  line_count: number
  created_at: string
  updated_at: string
}

export interface SourceChunk {
  id: string
  project_id: string
  source_id: string
  position: number
  kind: 'heading' | 'paragraph' | 'list' | 'code' | 'comment' | 'type' | 'method'
  heading_path: string[]
  start_line: number
  end_line: number
  content: string
  content_sha256: string
}

export interface SourceChunkList {
  items: SourceChunk[]
  page: number
  page_size: number
  total: number
}

export interface JavaCodeStructure {
  source_id: string
  symbols: {
    id: string
    kind: 'type' | 'field' | 'method'
    name: string
    qualified_name: string
    owner: string | null
    start_line: number
    end_line: number
  }[]
  calls: {
    id: string
    caller_id: string
    callee_ids: string[]
    callee_name: string
    line: number
    resolution: 'resolved' | 'ambiguous'
  }[]
  truncated: boolean
}

export interface SourceListItem {
  id: string
  project_id: string
  original_name: string
  source_type: string
  size_bytes: number
  status: ApiSource['status']
  created_at: string
  updated_at: string
  task_id: string | null
  task_status: ProcessingTask['status'] | null
}

export interface SourceList {
  items: SourceListItem[]
  page: number
  page_size: number
  total: number
}

export interface ProcessingTask {
  id: string
  project_id: string
  source_id: string
  type: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  stage: string
  progress: number
  error: Record<string, unknown> | null
  created_at: string
  updated_at: string
  started_at: string | null
  completed_at: string | null
}

export function listProjects(page = 1, pageSize = 20): Promise<ApiProjectList> {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  return apiRequest<ApiProjectList>(`/projects?${query}`)
}

export function createProject(input: {
  name: string
  description?: string
}): Promise<ApiProject> {
  return apiRequest<ApiProject>('/projects', {
    method: 'POST',
    body: JSON.stringify({
      name: input.name,
      description: input.description ?? '',
    }),
  })
}

export function uploadSource(
  projectId: string,
  file: File,
): Promise<SourceUploadResult> {
  const body = new FormData()
  body.append('file', file)
  body.append('source_type', file.name.toLowerCase().endsWith('.java') ? 'java' : 'markdown')
  return apiRequest<SourceUploadResult>(`/projects/${projectId}/sources`, {
    method: 'POST',
    body,
  })
}

export function getTask(taskId: string): Promise<ProcessingTask> {
  return apiRequest<ProcessingTask>(`/tasks/${taskId}`)
}

export function runTask(taskId: string): Promise<ProcessingTask> {
  return apiRequest<ProcessingTask>(`/tasks/${taskId}/run`, { method: 'POST' })
}

export function getSource(sourceId: string): Promise<ApiSource> {
  return apiRequest<ApiSource>(`/sources/${sourceId}`)
}

export function listSources(projectId: string, page = 1, pageSize = 20): Promise<SourceList> {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  return apiRequest<SourceList>(`/projects/${projectId}/sources?${query}`)
}

export function listSourceChunks(
  sourceId: string,
  page = 1,
  pageSize = 20,
): Promise<SourceChunkList> {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  return apiRequest<SourceChunkList>(`/sources/${sourceId}/chunks?${query}`)
}

export function getJavaCodeStructure(sourceId: string): Promise<JavaCodeStructure> {
  return apiRequest<JavaCodeStructure>(`/sources/${sourceId}/code-structure`)
}

export interface CandidateList {
  items: KnowledgeCandidate[]
  page: number
  page_size: number
  total: number
}

export interface ExtractionResult {
  task: ProcessingTask | null
  candidate_count: number
}

export function getExtraction(sourceId: string): Promise<ExtractionResult> {
  return apiRequest<ExtractionResult>(`/sources/${sourceId}/extraction`)
}

export function extractKnowledge(sourceId: string): Promise<ExtractionResult> {
  return apiRequest<ExtractionResult>(`/sources/${sourceId}/extract`, {
    method: 'POST', signal: AbortSignal.timeout(240000),
  })
}

export function listCandidates(projectId: string, sourceId: string, page = 1): Promise<CandidateList> {
  const query = new URLSearchParams({ source_id: sourceId, page: String(page), page_size: '20' })
  return apiRequest<CandidateList>(`/projects/${projectId}/reviews?${query}`)
}

export function resolveCandidate(decision: ReviewDecision): Promise<KnowledgeCandidate> {
  return apiRequest<KnowledgeCandidate>(`/reviews/${decision.id}/resolve`, {
    method: 'POST', body: JSON.stringify({ action: decision.action, changes: decision.changes ?? {} }),
  })
}

export function getProjectGraph(projectId: string, options: { centerId?: string; depth?: number; types?: string } = {}): Promise<ProjectGraphData> {
  const query = new URLSearchParams({ depth: String(options.depth ?? 1), limit: '100' })
  if (options.centerId) query.set('center_id', options.centerId)
  if (options.types) query.set('types', options.types)
  return apiRequest<ProjectGraphData>(`/projects/${projectId}/graph?${query}`)
}

export function getEntityDetail(id: string): Promise<EntityDetail> {
  return apiRequest<EntityDetail>(`/knowledge/entities/${id}`)
}

export function getRelationshipDetail(id: string): Promise<RelationshipDetail> {
  return apiRequest<RelationshipDetail>(`/knowledge/relationships/${id}`)
}

export function searchKnowledge(projectId: string, query: string, types = '', mode: KnowledgeSearchMode = 'keyword'): Promise<KnowledgeSearchResult> {
  const params = new URLSearchParams({ q: query, mode, top_k: '10' })
  if (types) params.set('types', types)
  return apiRequest<KnowledgeSearchResult>(`/projects/${projectId}/search?${params}`)
}

export function rebuildProjectEmbeddings(projectId: string): Promise<EmbeddingRebuildResult> {
  return apiRequest<EmbeddingRebuildResult>(`/projects/${projectId}/embeddings/rebuild`, {
    method: 'POST', signal: AbortSignal.timeout(240_000),
  })
}

export function askQuestion(projectId: string, question: string): Promise<QuestionAnswer> {
  return apiRequest<QuestionAnswer>(`/projects/${projectId}/questions`, {
    method: 'POST',
    body: JSON.stringify({ question }),
    signal: AbortSignal.timeout(240_000),
  })
}
