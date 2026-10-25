import { computed, onScopeDispose, reactive, ref, watch } from 'vue'
import { getEmbeddingStatus, rebuildProjectEmbeddings, searchKnowledge } from '../api/knowledgeAtlas'
import type { EmbeddingIndexStatus, KnowledgeSearchMode, KnowledgeSearchResult } from '../types'
import { useLatestRequest } from './useLatestRequest'

interface SearchContext { projectId: string | undefined; validAt: string }
interface SearchInput { query: string; types: string; mode: KnowledgeSearchMode }

/** Project/time-scoped search and explicit index maintenance, without page navigation. */
export function useKnowledgeSearch(context: () => SearchContext, describeError: (error: unknown) => string) {
  const search = useLatestRequest<KnowledgeSearchResult>(describeError)
  const index = useLatestRequest<EmbeddingIndexStatus>(describeError)
  const searchErrorAction = ref<'search' | 'rebuild'>('search')
  const searchNotice = ref('')
  // Clearing visible state cannot cancel an index write already sent to the server.
  const pendingRebuilds = reactive(new Set<string>())
  const searchRebuilding = computed(() => pendingRebuilds.has(context().projectId ?? ''))
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
    await index.run(() => getEmbeddingStatus(projectId, captured.validAt), () => sameContext(captured))
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

  async function rebuildSemanticIndex() {
    const captured = context()
    const projectId = captured.projectId
    if (disposed || !projectId || pendingRebuilds.has(projectId)) return
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
      const result = await rebuildProjectEmbeddings(projectId)
      if (!current()) return
      searchNotice.value = `语义索引已更新：新增或刷新 ${result.updated_count} 条，复用 ${result.reused_count} 条。`
      await loadIndexStatus()
      refreshed = current()
    } catch (error) {
      if (current()) search.error.value = describeError(error)
    } finally {
      pendingRebuilds.delete(projectId)
    }
    if (refreshed && current() && input && ['vector', 'hybrid', 'rrf'].includes(input.mode)) await retrySearch()
  }

  watch(() => [context().projectId, context().validAt], () => {
    clearSearch()
    index.clear()
  }, { flush: 'sync' })
  onScopeDispose(() => { disposed = true; clearSearch(); index.clear() })

  return {
    searchResult: search.result, searchLoading: search.loading, searchError: search.error,
    searchRebuilding, searchErrorAction, searchNotice,
    indexStatus: index.result, indexStatusLoading: index.loading, indexStatusError: index.error,
    runSearch, retrySearch, clearSearch, loadIndexStatus, clearIndexStatus: index.clear, rebuildSemanticIndex,
  }
}
