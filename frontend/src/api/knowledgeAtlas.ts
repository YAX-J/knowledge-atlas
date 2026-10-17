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
  status: 'queued'
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

