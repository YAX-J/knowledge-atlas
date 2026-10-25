import { effectScope, reactive } from 'vue'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useKnowledgeSearch } from '../src/composables/useKnowledgeSearch'
import * as api from '../src/api/knowledgeAtlas'
import type { EmbeddingIndexStatus, EmbeddingRebuildResult, KnowledgeSearchResult } from '../src/types'
import { ApiError } from '../src/api/client'

vi.mock('../src/api/knowledgeAtlas', () => ({
  searchKnowledge: vi.fn(), getEmbeddingStatus: vi.fn(), getEmbeddingJob: vi.fn(), rebuildProjectEmbeddings: vi.fn(),
}))

const scopes: ReturnType<typeof effectScope>[] = []
function setup() {
  const context = reactive<{ projectId: string | undefined; validAt: string }>({ projectId: 'first', validAt: '' })
  const scope = effectScope()
  scopes.push(scope)
  return { context, scope, state: scope.run(() => useKnowledgeSearch(() => ({ ...context }), String))! }
}
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (cause: Error) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const result: KnowledgeSearchResult = { query: 'Storage', mode: 'rrf', items: [], truncated: false,
  indexed_count: 1, eligible_count: 1, weights: null }
const rebuilt: EmbeddingRebuildResult = { model: 'test', dimensions: 1024, eligible_count: 1,
  updated_count: 1, reused_count: 0 }
const status: EmbeddingIndexStatus = { model: 'test', dimensions: 1024, configured: true,
  checked_at: '2026-10-25T00:00:00Z', eligible_count: 1, indexed_count: 1, missing_count: 0,
  stale_count: 0, current_count: 1, scanned_count: 1, scan_limit: 1000, truncated: false }

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(api.getEmbeddingJob).mockResolvedValue(null)
  vi.mocked(api.getEmbeddingStatus).mockResolvedValue(status)
  vi.mocked(api.rebuildProjectEmbeddings).mockResolvedValue(rebuilt)
  vi.mocked(api.searchKnowledge).mockResolvedValue(result)
})
afterEach(() => { scopes.splice(0).forEach(scope => scope.stop()) })

it('retries the submitted query, type, retrieval mode and effective time', async () => {
  const { context, state } = setup()
  context.validAt = '2026-10-24T00:00:00Z'
  vi.mocked(api.searchKnowledge).mockRejectedValueOnce(new Error('Retry me'))
  await state.runSearch('Storage', 'Decision', 'rrf')
  expect(state.searchError.value).toContain('Retry me')
  await state.retrySearch()
  expect(api.searchKnowledge).toHaveBeenLastCalledWith('first', 'Storage', 'Decision', 'rrf', context.validAt)
  expect(state.searchResult.value).toEqual(result)
  expect(state.searchErrorAction.value).toBe('search')
})

it('rejects a late search even after leaving and returning to the same project and time', async () => {
  const { context, state } = setup()
  const old = deferred<KnowledgeSearchResult>()
  vi.mocked(api.searchKnowledge).mockReturnValueOnce(old.promise)
  const request = state.runSearch('Old', '', 'vector')
  context.projectId = 'second'
  context.projectId = 'first'
  context.validAt = '2026-10-24T00:00:00Z'
  context.validAt = ''
  old.resolve(result)
  await request
  await state.retrySearch()
  expect(state.searchResult.value).toBeNull()
  expect(state.searchLoading.value).toBe(false)
  expect(api.searchKnowledge).toHaveBeenCalledTimes(1)
})

it('preserves the latest search loading/result when an older request fails', async () => {
  const { state } = setup()
  const old = deferred<KnowledgeSearchResult>(), latest = deferred<KnowledgeSearchResult>()
  vi.mocked(api.searchKnowledge).mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise)
  const first = state.runSearch('Old', '', 'keyword')
  const second = state.runSearch('New', '', 'bm25')
  old.reject(new Error('Old error'))
  await first
  expect(state.searchLoading.value).toBe(true)
  expect(state.searchError.value).toBe('')
  latest.resolve({ ...result, query: 'New', mode: 'bm25' })
  await second
  expect(state.searchResult.value?.query).toBe('New')
})

it('clears search and retry parameters without letting a late result restore them', async () => {
  const { state } = setup()
  const old = deferred<KnowledgeSearchResult>()
  vi.mocked(api.searchKnowledge).mockReturnValueOnce(old.promise)
  const request = state.runSearch('Old', '', 'bm25')
  state.clearSearch()
  old.resolve(result)
  await request
  await state.retrySearch()
  expect(api.searchKnowledge).toHaveBeenCalledTimes(1)
  expect(state.searchResult.value).toBeNull()
})

it('invalidates index reads when time changes and supports an explicit retry after failure', async () => {
  const { context, state } = setup()
  const old = deferred<EmbeddingIndexStatus>()
  vi.mocked(api.getEmbeddingStatus).mockReturnValueOnce(old.promise).mockRejectedValueOnce(new Error('Offline'))
  const request = state.loadIndexStatus()
  context.validAt = '2026-10-24T00:00:00Z'
  await state.loadIndexStatus()
  old.resolve(status)
  await request
  expect(state.indexStatus.value).toBeNull()
  expect(state.indexStatusError.value).toContain('Offline')
  await state.loadIndexStatus()
  expect(api.getEmbeddingStatus).toHaveBeenLastCalledWith('first', context.validAt)
  expect(state.indexStatus.value).toEqual(status)
})

it('blocks duplicate rebuilds and searches until the outstanding rebuild finishes after clear', async () => {
  const { state } = setup()
  const pending = deferred<EmbeddingRebuildResult>()
  vi.mocked(api.rebuildProjectEmbeddings).mockReturnValueOnce(pending.promise)
  const request = state.rebuildSemanticIndex()
  state.clearSearch()
  await state.rebuildSemanticIndex()
  await state.runSearch('Storage', '', 'vector')
  expect(state.searchRebuilding.value).toBe(true)
  expect(api.rebuildProjectEmbeddings).toHaveBeenCalledTimes(1)
  expect(api.searchKnowledge).not.toHaveBeenCalled()
  pending.resolve(rebuilt)
  await request
  expect(state.searchRebuilding.value).toBe(false)
  expect(state.searchNotice.value).toBe('')
  expect(api.getEmbeddingStatus).not.toHaveBeenCalled()
  await state.rebuildSemanticIndex()
  expect(api.rebuildProjectEmbeddings).toHaveBeenCalledTimes(2)
})

it('isolates rebuilding projects and drops completion after a project round trip', async () => {
  const { context, state } = setup()
  const old = deferred<EmbeddingRebuildResult>()
  vi.mocked(api.rebuildProjectEmbeddings).mockReturnValueOnce(old.promise)
  const request = state.rebuildSemanticIndex()
  context.projectId = 'second'
  expect(state.searchRebuilding.value).toBe(false)
  await state.rebuildSemanticIndex()
  expect(state.searchNotice.value).toContain('语义索引已更新')
  context.projectId = 'first'
  expect(state.searchRebuilding.value).toBe(true)
  await state.rebuildSemanticIndex()
  expect(api.rebuildProjectEmbeddings).toHaveBeenCalledTimes(2)
  old.resolve(rebuilt)
  await request
  expect(state.searchNotice.value).toBe('')
  expect(state.indexStatus.value).toBeNull()
})

it('refreshes status and the last vector search only after successful rebuild', async () => {
  const { state } = setup()
  await state.runSearch('Storage', 'Decision', 'rrf')
  await state.rebuildSemanticIndex()
  expect(api.getEmbeddingStatus).toHaveBeenCalledExactlyOnceWith('first', '')
  expect(api.searchKnowledge).toHaveBeenCalledTimes(2)
  expect(api.searchKnowledge).toHaveBeenLastCalledWith('first', 'Storage', 'Decision', 'rrf', '')
  expect(state.searchNotice.value).toContain('新增或刷新 1 条')
  expect(state.searchRebuilding.value).toBe(false)
})

it('keeps BM25 results and avoids rerunning lexical search after an index update', async () => {
  const { state } = setup()
  const lexical = { ...result, mode: 'bm25' as const }
  vi.mocked(api.searchKnowledge).mockResolvedValueOnce(lexical)
  await state.runSearch('Storage', '', 'bm25')
  await state.rebuildSemanticIndex()
  expect(api.searchKnowledge).toHaveBeenCalledTimes(1)
  expect(state.searchResult.value).toEqual(lexical)
})

it('separates rebuild failure retry from search retry and releases the rebuild guard', async () => {
  const { state } = setup()
  vi.mocked(api.rebuildProjectEmbeddings).mockRejectedValueOnce(new Error('Index failed'))
  await state.rebuildSemanticIndex()
  expect(state.searchError.value).toContain('Index failed')
  expect(state.searchErrorAction.value).toBe('rebuild')
  expect(state.searchRebuilding.value).toBe(false)
  await state.rebuildSemanticIndex()
  expect(state.searchError.value).toBe('')
  expect(api.rebuildProjectEmbeddings).toHaveBeenCalledTimes(2)
})

it('does not relaunch search when context changes during the post-rebuild status read', async () => {
  const { context, state } = setup()
  await state.runSearch('Storage', '', 'vector')
  const pending = deferred<EmbeddingIndexStatus>()
  vi.mocked(api.getEmbeddingStatus).mockReturnValueOnce(pending.promise)
  const request = state.rebuildSemanticIndex()
  await Promise.resolve()
  context.validAt = '2026-10-24T00:00:00Z'
  pending.resolve(status)
  await request
  expect(api.searchKnowledge).toHaveBeenCalledTimes(1)
  expect(state.indexStatus.value).toBeNull()
  expect(state.searchNotice.value).toBe('')
})

it('does not call providers without a project, for empty queries or after disposal', async () => {
  const { context, scope, state } = setup()
  await state.runSearch('  ', '', 'vector')
  context.projectId = undefined
  await state.runSearch('Storage', '', 'vector')
  await state.loadIndexStatus()
  await state.rebuildSemanticIndex()
  context.projectId = 'first'
  const pending = deferred<EmbeddingRebuildResult>()
  vi.mocked(api.rebuildProjectEmbeddings).mockReturnValueOnce(pending.promise)
  const request = state.rebuildSemanticIndex()
  scope.stop()
  pending.reject(new Error('Disposed error'))
  await request
  await state.runSearch('Storage', '', 'vector')
  await state.loadIndexStatus()
  await state.rebuildSemanticIndex()
  expect(api.searchKnowledge).not.toHaveBeenCalled()
  expect(api.getEmbeddingStatus).not.toHaveBeenCalled()
  expect(api.rebuildProjectEmbeddings).toHaveBeenCalledTimes(1)
  expect(state.searchError.value).toBe('')
})

it('restores a running server rebuild after a new page instance and checks status instead of retrying a write', async () => {
  const { state } = setup()
  const job = { id: 'execution', project_id: 'first', status: 'running' as const, interrupted: false,
    started_at: status.checked_at, lease_expires_at: status.checked_at, completed_at: null, result: null, error: null }
  vi.mocked(api.getEmbeddingJob).mockResolvedValue(job)
  await state.loadIndexStatus()
  expect(state.searchRebuilding.value).toBe(true)
  await state.rebuildSemanticIndex()
  expect(api.rebuildProjectEmbeddings).not.toHaveBeenCalled()
  vi.mocked(api.getEmbeddingJob).mockResolvedValue(null)
  await state.loadIndexStatus()
  vi.mocked(api.rebuildProjectEmbeddings).mockRejectedValueOnce(new ApiError(0, {error:{code:'REQUEST_RESULT_UNKNOWN',message:'Unknown'}}))
  await state.rebuildSemanticIndex()
  expect(state.searchErrorAction.value).toBe('inspect')
  expect(api.rebuildProjectEmbeddings).toHaveBeenCalledTimes(1)
})
