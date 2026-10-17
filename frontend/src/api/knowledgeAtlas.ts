import { apiRequest } from './client'

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
  kind: 'heading' | 'paragraph' | 'list' | 'code'
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

export interface SourceListItem {
  id: string
  project_id: string
  original_name: string
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

export function uploadMarkdown(
  projectId: string,
  file: File,
): Promise<SourceUploadResult> {
  const body = new FormData()
  body.append('file', file)
  body.append('source_type', 'markdown')
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

