import { apiRequest } from './client'
import type { GovernanceResult, KnowledgeChange, KnowledgeChangeInput, KnowledgeChangeList, KnowledgeHistory } from '../types'
import type { EmbeddingRebuildResult, EntityDetail, KnowledgeCandidate, KnowledgeSearchMode, KnowledgeSearchResult, Neo4jGraphData, Neo4jSnapshot, ProjectGraphData, QuestionAnswer, RelationshipDetail, ReviewDecision } from '../types'

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
  repository_id: string | null
  repository_name: string | null
  git_url: string | null
  original_name: string
  relative_path: string | null
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
  language: string
  has_syntax_errors: boolean
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
  related_types: {
    id: string
    source_id: string
    source_path: string
    name: string
    qualified_name: string
    start_line: number
    end_line: number
  }[]
  type_relationships: {
    id: string
    source_symbol_id: string
    target_ids: string[]
    target_name: string
    kind: 'extends' | 'implements'
    line: number
    resolution: 'resolved' | 'ambiguous'
  }[]
  related_methods: {
    id: string
    source_id: string
    source_path: string
    owner_qualified_name: string
    name: string
    qualified_name: string
    start_line: number
    end_line: number
  }[]
  cross_file_calls: {
    id: string
    caller_id: string
    target_ids: string[]
    receiver: string
    callee_name: string
    line: number
    resolution: 'resolved' | 'ambiguous'
  }[]
  truncated: boolean
}

export interface AgentCallAnalysis {
  context?: { snapshot_id: string | null; commit_sha: string | null; policy: string }
  source_id: string
  language: string
  model: string | null
  prompt_version: string
  calls: {
    id: string
    caller_id: string | null
    target_ids: string[]
    receiver: string | null
    callee_name: string
    line: number
    column: number
    call_quote: string
    resolution: 'resolved' | 'ambiguous' | 'unresolved'
    confidence: number
    resolution_basis: string
  }[]
  related_symbols: {
    id: string
    source_id: string
    source_path: string
    language: string
    name: string
    qualified_name: string
    start_line: number
    end_line: number
    quote: string
  }[]
  scanned_source_count: number
  detected_call_count: number
  candidate_call_count: number
  provider_call_count: number
  strategy: 'single_step' | 'tools' | 'semantic'
  candidate_generation?: string
  uncovered_call_count?: number
  semantic_diagnostics?: Record<string, unknown>[]
  tool_call_count: number
  tool_trace: { name: string; status: string; result_characters: number; duration_ms: number }[]
  truncated: boolean
  has_syntax_errors: boolean
}

export type CodeSymbolHit = JavaCodeStructure['symbols'][number] & {
  language: string
  source_id: string
  source_path: string
  repository_id: string | null
  repository_name: string | null
  task_id: string | null
  chunk_id: string | null
  chunk_position: number | null
  git_url: string | null
}

export interface CodeSymbolSearchInput {
  query: string
  repositoryId: string
  kind: '' | 'type' | 'field' | 'method'
}

export interface CodeSymbolSearchResult {
  query: string
  items: CodeSymbolHit[]
  scanned_source_count: number
  matched_count: number
  truncated: boolean
  has_syntax_errors: boolean
}

export interface SourceListItem {
  id: string
  project_id: string
  repository_id: string | null
  repository_name: string | null
  git_url: string | null
  original_name: string
  relative_path: string | null
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

export interface SourceRepository {
  id: string
  project_id: string
  name: string
  kind: 'local_folder' | 'git_remote'
  provider: 'github' | null
  remote_owner: string | null
  remote_name: string | null
  remote_url: string | null
  provider_repository_id: string | null
  created_at: string
  updated_at: string
}

export interface SourceRepositoryList {
  items: SourceRepository[]
  page: number
  page_size: number
  total: number
}

export interface GithubRepositorySyncResult {
  pending_directories?: number
  tree_complete?: boolean
  traversal_blocked?: boolean
  continuation_snapshot_id?: string | null
  completed_files?: number
  remaining_files?: number
  total_supported_files?: number
  access?: 'public' | 'private' | 'unknown'
  repository_id: string
  snapshot_id: string
  ref: string
  commit_sha: string
  commit_url: string | null
  imported_count: number
  reused_count: number
  unchanged_count: number
  renamed_count: number
  deleted_count: number
  skipped_count: number
  truncated: boolean
  deletion_detection_complete: boolean
  items: {
    path: string
    previous_path: string | null
    source_id: string | null
    task_id: string | null
    status: 'imported' | 'reused' | 'unchanged' | 'renamed' | 'deleted' | 'skipped'
    error_code: string | null
  }[]
}

export interface GithubWorkItemImportResult {
  repository_id: string
  imported_count: number
  reused_count: number
  skipped_count: number
  review_imported_count: number
  review_reused_count: number
  review_skipped_count: number
  truncated: boolean
  items: {
    number: number
    item_type: 'issue' | 'pull_request'
    title: string
    html_url: string
    source_id: string | null
    task_id: string | null
    status: 'imported' | 'reused' | 'skipped'
    comments_truncated: boolean
    review_source_id: string | null
    review_task_id: string | null
    review_status: 'imported' | 'reused' | 'skipped' | 'not_requested'
    reviews_count: number
    review_comments_count: number
    reviews_truncated: boolean
    review_comments_truncated: boolean
    review_threads_status: 'included' | 'token_required' | 'not_requested'
    review_threads_count: number
    resolved_review_threads_count: number
    review_threads_truncated: boolean
    error_code: string | null
    review_error_code: string | null
  }[]
}

export interface RepositorySnapshotList {
  items: {
    id: string
    repository_id: string
    ref: string
    commit_sha: string
    tree_sha: string
    commit_url: string | null
    commit_message: string
    commit_source_id: string | null
    commit_task_id: string | null
    committed_at: string | null
    truncated: boolean
    deletion_detection_complete: boolean
    file_count: number
    imported_count: number
    reused_count: number
    unchanged_count: number
    renamed_count: number
    deleted_count: number
    skipped_count: number
    downloaded_bytes: number
    created_at: string
  }[]
  page: number
  page_size: number
  total: number
}

export interface RepositorySnapshotFile {
  id: string
  path: string
  previous_path: string | null
  blob_sha: string
  size_bytes: number
  status: 'imported' | 'reused' | 'unchanged' | 'renamed' | 'deleted' | 'skipped'
  error_code: string | null
  source_id: string | null
  task_id: string | null
  source_status: string | null
  git_url: string | null
}

export interface RepositorySnapshotFileList {
  snapshot_id: string
  repository_id: string
  commit_sha: string
  truncated: boolean
  deletion_detection_complete: boolean
  items: RepositorySnapshotFile[]
  page: number
  page_size: number
  total: number
}

export function listSnapshotFiles(projectId: string, repositoryId: string, snapshotId: string, page = 1): Promise<RepositorySnapshotFileList> {
  const query = new URLSearchParams({ page: String(page), page_size: '20' })
  return apiRequest<RepositorySnapshotFileList>(`/projects/${projectId}/repositories/${repositoryId}/snapshots/${snapshotId}/files?${query}`)
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

export interface SnapshotCommitSource {
  snapshot_id: string
  source_id: string
  task_id: string
  status: ProcessingTask['status']
  reused: boolean
  git_url: string
}

export function importSnapshotCommit(projectId: string, repositoryId: string, snapshotId: string): Promise<SnapshotCommitSource> {
  return apiRequest<SnapshotCommitSource>(`/projects/${projectId}/repositories/${repositoryId}/snapshots/${snapshotId}/commit-source`, { method: 'POST' })
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

export function getProject(projectId: string): Promise<ApiProject> {
  return apiRequest(`/projects/${encodeURIComponent(projectId)}`)
}

export function uploadSource(
  projectId: string,
  file: File,
  relativePath?: string,
  repositoryId?: string,
): Promise<SourceUploadResult> {
  const body = new FormData()
  body.append('file', file)
  if (relativePath) body.append('relative_path', relativePath)
  if (repositoryId) body.append('repository_id', repositoryId)
  return apiRequest<SourceUploadResult>(`/projects/${projectId}/sources`, {
    method: 'POST',
    body,
  })
}

export function resolveLocalRepository(
  projectId: string,
  name: string,
): Promise<SourceRepository> {
  return apiRequest<SourceRepository>(`/projects/${projectId}/repositories/resolve`, {
    method: 'POST',
    body: JSON.stringify({ name, kind: 'local_folder' }),
  })
}

export function listRepositories(
  projectId: string,
  page = 1,
  pageSize = 20,
): Promise<SourceRepositoryList> {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  return apiRequest<SourceRepositoryList>(`/projects/${projectId}/repositories?${query}`)
}

export function resolveGithubRepository(
  projectId: string,
  remoteUrl: string,
  localRepositoryId?: string,
): Promise<SourceRepository> {
  return apiRequest<SourceRepository>(`/projects/${projectId}/repositories/resolve-github`, {
    method: 'POST',
    body: JSON.stringify({
      remote_url: remoteUrl,
      local_repository_id: localRepositoryId || null,
    }),
  })
}

export function syncGithubRepository(
  projectId: string,
  repositoryId: string,
  ref?: string,
  rescan = false,
  continueFromSnapshot?: string,
): Promise<GithubRepositorySyncResult> {
  return apiRequest<GithubRepositorySyncResult>(
    `/projects/${projectId}/repositories/${repositoryId}/sync-github`,
    {
      method: 'POST',
      body: JSON.stringify({ ref: ref?.trim() || null, rescan, ...(continueFromSnapshot ? { continue_from_snapshot: continueFromSnapshot } : {}) }),
      signal: AbortSignal.timeout(120000),
    },
  )
}

export function importGithubWorkItems(
  projectId: string,
  repositoryId: string,
): Promise<GithubWorkItemImportResult> {
  return apiRequest<GithubWorkItemImportResult>(
    `/projects/${projectId}/repositories/${repositoryId}/import-github-work-items`,
    {
      method: 'POST',
      body: JSON.stringify({
        state: 'all',
        item_type: 'all',
        include_comments: true,
        include_reviews: true,
        include_review_threads: true,
        limit: 20,
      }),
      signal: AbortSignal.timeout(120000),
    },
  )
}

export function listRepositorySnapshots(
  projectId: string,
  repositoryId: string,
  page = 1,
  pageSize = 20,
): Promise<RepositorySnapshotList> {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  return apiRequest<RepositorySnapshotList>(
    `/projects/${projectId}/repositories/${repositoryId}/snapshots?${query}`,
  )
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

export function listSources(projectId: string, page = 1, pageSize = 20, filters?: import('../types').SourceFilters): Promise<SourceList> {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (filters?.query.trim()) query.set('q', filters.query.trim())
  if (filters?.type) query.set('source_type', filters.type)
  if (filters?.status) query.set('source_status', filters.status)
  return apiRequest<SourceList>(`/projects/${projectId}/sources?${query}`)
}

export function getProjectSourceChunk(projectId: string, sourceId: string, chunkId: string): Promise<SourceChunk> {
  return apiRequest<SourceChunk>(`/projects/${projectId}/sources/${sourceId}/chunks/${chunkId}`)
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

export interface CodeAnalysisContexts {
  default_snapshot_id: string | null
  snapshots: { id: string; commit_sha: string; ref: string; truncated: boolean }[]
  version_groups: { path: string; versions: { id: string; created_at: string; size_bytes: number }[]; truncated: boolean }[]
  truncated: boolean
}
export interface CodeAnalysisSelection { snapshotId?: string; versionIds?: string[] }
export function getCodeAnalysisContexts(sourceId: string): Promise<CodeAnalysisContexts> {
  return apiRequest(`/sources/${sourceId}/analysis-contexts`)
}
export function analyzeAgentCalls(sourceId: string, strategy: 'single_step' | 'tools' | 'semantic' = 'single_step', selection: CodeAnalysisSelection = {}): Promise<AgentCallAnalysis> {
  const query = new URLSearchParams({ strategy })
  if (selection.snapshotId) query.set('snapshot_id', selection.snapshotId)
  for (const identifier of selection.versionIds ?? []) query.append('version_ids', identifier)
  return apiRequest<AgentCallAnalysis>(`/sources/${sourceId}/agent-call-analysis?${query}`, {
    method: 'POST', signal: AbortSignal.timeout(strategy === 'tools' ? 900_000 : 240_000),
  })
}

export function searchCodeSymbols(projectId: string, input: CodeSymbolSearchInput): Promise<CodeSymbolSearchResult> {
  const query = new URLSearchParams({ q: input.query, limit: '50' })
  if (input.repositoryId) query.set('repository_id', input.repositoryId)
  if (input.kind) query.set('kind', input.kind)
  return apiRequest<CodeSymbolSearchResult>(`/projects/${projectId}/code-symbols?${query}`)
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
  review_counts?: { pending: number; confirmed: number; rejected: number }
}

export function getExtraction(sourceId: string): Promise<ExtractionResult> {
  return apiRequest<ExtractionResult>(`/sources/${sourceId}/extraction`)
}

export function extractKnowledge(sourceId: string): Promise<ExtractionResult> {
  return apiRequest<ExtractionResult>(`/sources/${sourceId}/extract`, {
    method: 'POST', signal: AbortSignal.timeout(240000),
  })
}

export function listCandidates(projectId: string, sourceId: string, page = 1, filters?: import('../types').ReviewFilters): Promise<CandidateList> {
  const query = new URLSearchParams({ source_id: sourceId, page: String(page), page_size: '20' })
  if (filters?.status) query.set('review_status', filters.status)
  if (filters?.kind) query.set('kind', filters.kind)
  if (filters?.query.trim()) query.set('q', filters.query.trim())
  return apiRequest<CandidateList>(`/projects/${projectId}/reviews?${query}`)
}

export function resolveCandidate(decision: ReviewDecision): Promise<KnowledgeCandidate> {
  return apiRequest<KnowledgeCandidate>(`/reviews/${decision.id}/resolve`, {
    method: 'POST', body: JSON.stringify({ action: decision.action, changes: decision.changes ?? {} }),
  })
}

export function resolveCandidatesBatch(projectId: string, sourceId: string, reviewIds: string[], action: 'confirm' | 'reject') {
  return apiRequest<{ items: KnowledgeCandidate[]; processed_count: number }>(`/projects/${projectId}/reviews/resolve-batch`, {
    method: 'POST', body: JSON.stringify({ source_id: sourceId, review_ids: reviewIds, action }),
  })
}

export function getEmbeddingStatus(projectId: string, validAt = '') {
  const query = validAt ? `?${new URLSearchParams({ valid_at: validAt })}` : ''
  return apiRequest<import('../types').EmbeddingIndexStatus>(`/projects/${projectId}/embeddings/status${query}`)
}

interface GraphQuery { centerId?: string; depth?: number; types?: string }

function graphQuery(options: GraphQuery) {
  const query = new URLSearchParams({ depth: String(options.depth ?? 1), limit: '100' })
  if (options.centerId) query.set('center_id', options.centerId)
  if (options.types) query.set('types', options.types)
  return query
}

export function getProjectGraph(projectId: string, options: GraphQuery & { validAt?: string } = {}): Promise<ProjectGraphData> {
  const query = graphQuery(options)
  if (options.validAt) query.set('valid_at', options.validAt)
  return apiRequest<ProjectGraphData>(`/projects/${projectId}/graph?${query}`)
}

export function getNeo4jGraph(projectId: string, options: GraphQuery = {}): Promise<Neo4jGraphData> {
  return apiRequest(`/projects/${projectId}/graph/neo4j?${graphQuery(options)}`)
}

export function syncNeo4jGraph(projectId: string): Promise<Neo4jSnapshot> {
  return apiRequest(`/projects/${projectId}/graph/neo4j/sync`, {
    method: 'POST', signal: AbortSignal.timeout(75_000),
  })
}

export function getEntityDetail(id: string, validAt = ''): Promise<EntityDetail> {
  const query = validAt ? `?${new URLSearchParams({ valid_at: validAt })}` : ''
  return apiRequest<EntityDetail>(`/knowledge/entities/${id}${query}`)
}

export function getRelationshipDetail(id: string, validAt = ''): Promise<RelationshipDetail> {
  const query = validAt ? `?${new URLSearchParams({ valid_at: validAt })}` : ''
  return apiRequest<RelationshipDetail>(`/knowledge/relationships/${id}${query}`)
}

export function searchKnowledge(projectId: string, query: string, types = '', mode: KnowledgeSearchMode = 'keyword', validAt = ''): Promise<KnowledgeSearchResult> {
  const params = new URLSearchParams({ q: query, mode, top_k: '10' })
  if (types) params.set('types', types)
  if (validAt) params.set('valid_at', validAt)
  return apiRequest<KnowledgeSearchResult>(`/projects/${projectId}/search?${params}`, {
    signal: AbortSignal.timeout(['vector', 'hybrid', 'rrf'].includes(mode) ? 240_000 : 30_000),
  })
}

export function listKnowledgeChanges(projectId: string, page = 1): Promise<KnowledgeChangeList> {
  return apiRequest(`/projects/${projectId}/knowledge-changes?page=${page}&page_size=10`)
}

export function proposeKnowledgeChange(projectId: string, input: KnowledgeChangeInput): Promise<KnowledgeChange> {
  return apiRequest(`/projects/${projectId}/knowledge-changes`, { method: 'POST', body: JSON.stringify(input) })
}

export function resolveKnowledgeChange(projectId: string, id: string, action: 'confirm' | 'reject'): Promise<KnowledgeChange> {
  return apiRequest(`/projects/${projectId}/knowledge-changes/${id}/resolve`, { method: 'POST', body: JSON.stringify({ action }) })
}

export function getKnowledgeHistory(projectId: string, entityId: string): Promise<KnowledgeHistory> {
  return apiRequest(`/projects/${projectId}/knowledge/entities/${entityId}/history`)
}

export function inspectGovernance(projectId: string, kind: import('../types').GovernanceKind | '' = ''): Promise<GovernanceResult> {
  return apiRequest(`/projects/${projectId}/governance${kind ? `?${new URLSearchParams({ kind })}` : ''}`)
}

export function getEmbeddingJob(projectId: string) {
  return apiRequest<import('../types').EmbeddingJob | null>(`/projects/${projectId}/embeddings/rebuild-status`)
}

export function listKnowledgeRetirements(projectId: string, page = 1) {
  return apiRequest<import('../types').RetirementList>(`/projects/${projectId}/knowledge-retirements?page=${page}&page_size=20`)
}

export function retireKnowledge(projectId: string, input: import('../types').RetirementInput & { request_id: string }) {
  return apiRequest<import('../types').KnowledgeRetirement>(`/projects/${projectId}/knowledge-retirements`, {
    method: 'POST', body: JSON.stringify(input),
  })
}

export function rebuildProjectEmbeddings(projectId: string, retryInterrupted = false): Promise<EmbeddingRebuildResult> {
  return apiRequest<EmbeddingRebuildResult>(`/projects/${projectId}/embeddings/rebuild${retryInterrupted ? '?retry_interrupted=true' : ''}`, {
    method: 'POST', signal: AbortSignal.timeout(240_000),
  })
}

export function askQuestion(projectId: string, question: string, retrievalMode: import('../types').QuestionRetrievalMode = 'rrf'): Promise<QuestionAnswer> {
  return apiRequest<QuestionAnswer>(`/projects/${projectId}/questions`, {
    method: 'POST',
    body: JSON.stringify({ question, retrieval_mode: retrievalMode }),
    signal: AbortSignal.timeout(420_000),
  })
}
