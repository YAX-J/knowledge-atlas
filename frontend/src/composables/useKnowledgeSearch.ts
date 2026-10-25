import { computed, onScopeDispose, reactive, ref, watch } from 'vue'
import { getEmbeddingJob, getEmbeddingStatus, rebuildProjectEmbeddings, searchKnowledge } from '../api/knowledgeAtlas'
import { ApiError } from '../api/client'
import type { EmbeddingIndexStatus, EmbeddingJob, KnowledgeSearchMode, KnowledgeSearchResult } from '../types'
import { useLatestRequest } from './useLatestRequest'

interface SearchContext { projectId: string | undefined; validAt: string }
interface SearchInput { query: string; types: string; mode: KnowledgeSearchMode }

/** Project/time-scoped search and explicit index maintenance, without page navigation. */
export function useKnowledgeSearch(context: () => SearchContext, describeError: (error: unknown) => string) {
  const search = useLatestRequest<KnowledgeSearchResult>(describeError)
  const index = useLatestRequest<EmbeddingIndexStatus>(describeError)
  const jobs = useLatestRequest<EmbeddingJob | null>(describeError)
  const knownJob = ref<EmbeddingJob | null>(null)
  const searchErrorAction = ref<'search' | 'rebuild' | 'inspect'>('search')
  const searchNotice = ref('')
  // Clearing visible state cannot cancel an index write already sent to the server.
  const pendingRebuilds = reactive(new Set<string>())
  const searchRebuilding = computed(() => pendingRebuilds.has(context().projectId ?? '') ||
    (knownJob.value?.status === 'running' && !knownJob.value.interrupted))
  let input: SearchInput | null = null
  let generation = 0
  let disposed = false

  function clearSearch() {
    generation++
    search.clear()
    searchErrorAction.value = 'search'
    searchNotice.value = ''
    input = null
  }

  function sameContext(captured: SearchContext) {
    const current = context()
    return !disposed && current.projectId === captured.projectId && current.validAt === captured.validAt
  }

  async function loadIndexStatus() {
    const captured = context()
    const projectId = captured.projectId
    if (disposed || !projectId) return
    await Promise.all([
      index.run(() => getEmbeddingStatus(projectId, captured.validAt), () => sameContext(captured)),
      (async () => {
        await jobs.run(() => getEmbeddingJob(projectId), () => sameContext(captured))
        if (sameContext(captured) && !jobs.loading.value && !jobs.error.value) knownJob.value = jobs.result.value
      })(),
    ])
  }

  async function runSearch(query: string, types: string, mode: KnowledgeSearchMode) {
    const captured = context()
    const projectId = captured.projectId
    if (disposed || !projectId || searchRebuilding.value || !query.trim()) return
    input = { query, types, mode }
    searchErrorAction.value = 'search'
    await search.run(() => searchKnowledge(projectId, query, types, mode, captured.validAt),
      () => sameContext(captured))
  }

  async function retrySearch() {
    if (input) await runSearch(input.query, input.types, input.mode)
  }

  async function rebuildSemanticIndex(retryInterrupted = false) {
    const captured = context()
    const projectId = captured.projectId
    if (disposed || !projectId || searchRebuilding.value) return
    const request = generation
    const current = () => request === generation && sameContext(captured)
    pendingRebuilds.add(projectId)
    const previousResult = search.result.value
    search.clear()
    search.result.value = previousResult
    searchErrorAction.value = 'rebuild'
    searchNotice.value = ''
    let refreshed = false
    try {
      const result = retryInterrupted ? await rebuildProjectEmbeddings(projectId, true) : await rebuildProjectEmbeddings(projectId)
      if (!current()) return
      searchNotice.value = `语义索引已更新：新增或刷新 ${result.updated_count} 条，复用 ${result.reused_count} 条。`
      await loadIndexStatus()
      refreshed = current()
    } catch (error) {
      if (current()) {
        search.error.value = describeError(error)
        if (error instanceof ApiError && ['REQUEST_RESULT_UNKNOWN', 'EMBEDDING_REBUILD_RUNNING', 'EMBEDDING_REBUILD_INTERRUPTED'].includes(error.code)) {
          searchErrorAction.value = 'inspect'
          await loadIndexStatus()
        }
      }
    } finally {
      pendingRebuilds.delete(projectId)
    }
    if (refreshed && current() && input && ['vector', 'hybrid', 'rrf'].includes(input.mode)) await retrySearch()
  }

  watch(() => [context().projectId, context().validAt], () => {
    clearSearch()
    index.clear()
    jobs.clear()
    knownJob.value = null
  }, { flush: 'sync' })
  onScopeDispose(() => { disposed = true; clearSearch(); index.clear(); jobs.clear(); knownJob.value = null })

  return {
    searchResult: search.result, searchLoading: search.loading, searchError: search.error,
    searchRebuilding, searchErrorAction, searchNotice,
    indexStatus: index.result, indexStatusLoading: index.loading, indexStatusError: index.error,
    embeddingJob: knownJob, embeddingJobError: jobs.error,
    runSearch, retrySearch, clearSearch, loadIndexStatus, clearIndexStatus: index.clear, rebuildSemanticIndex,
  }
}
