import { nextTick, onScopeDispose, ref, type Ref } from 'vue'
import { getProjectSourceChunk } from '../api/knowledgeAtlas'
import type { ApiProject, SourceChunkList } from '../api/knowledgeAtlas'
import type { EvidenceLocator, IngestionErrors, WorkspaceNav } from '../types'

interface Options {
  project: Ref<ApiProject | null>; activeNav: Ref<WorkspaceNav>; errors: IngestionErrors
  chunks: Ref<SourceChunkList | null>; focusedChunkId: Ref<string>; notice: Ref<string>
  selectedSourceId: Ref<string>; selectedTaskId: Ref<string | null>
  locked: () => boolean; clearSourceSelection: () => void
  refreshSource: (page?: number) => Promise<void>; errorMessage: (error: unknown) => string
}

export function useEvidenceNavigation(options: Options) {
  const { project, activeNav, errors, chunks, focusedChunkId, notice, selectedSourceId,
    selectedTaskId, locked, clearSourceSelection, refreshSource, errorMessage } = options
  const evidenceTarget = ref<EvidenceLocator | null>(null)
  const evidenceNavigationLoading = ref(false)
  const evidenceNavigationError = ref('')
  let evidenceNavigationRequest = 0

  function clearEvidenceNavigation() {
    evidenceNavigationRequest++
    evidenceTarget.value = null
    evidenceNavigationLoading.value = false
    evidenceNavigationError.value = ''
  }

  async function openEvidence(locator: EvidenceLocator) {
    if (!project.value || locked()) return
    const projectId = project.value.id
    clearSourceSelection()
    notice.value = ''
    evidenceTarget.value = { source_id: locator.source_id, chunk_id: locator.chunk_id }
    evidenceNavigationLoading.value = true
    activeNav.value = 'sources'
    const request = ++evidenceNavigationRequest
    const current = () => request === evidenceNavigationRequest && project.value?.id === projectId
    try {
      const chunk = await getProjectSourceChunk(projectId, locator.source_id, locator.chunk_id)
      if (!current()) return
      selectedSourceId.value = chunk.source_id
      selectedTaskId.value = null // Evidence reads do not require a surviving parsing task.
      await refreshSource(Math.floor(chunk.position / 20) + 1)
      if (!current()) return
      if (!chunks.value?.items.some(item => item.id === chunk.id)) {
        evidenceNavigationError.value = errors.detail || errors.chunks || '证据分块未能在当前解析结果中定位，请刷新资料后重试。'
        return
      }
      focusedChunkId.value = chunk.id
      await nextTick()
      if (!current()) return
      const target = document.getElementById(`source-chunk-${chunk.id}`)
      if (!target) {
        evidenceNavigationError.value = '当前资料尚不能展示此分块，请检查解析状态后重试。'
        return
      }
      clearEvidenceNavigation()
      notice.value = `已定位证据原文第 ${chunk.start_line}–${chunk.end_line} 行。`
      target.focus({ preventScroll: true })
      target.scrollIntoView({ block: 'center', behavior: 'instant' })
    } catch (error) {
      if (current()) evidenceNavigationError.value = errorMessage(error)
    } finally {
      if (current()) {
        evidenceNavigationLoading.value = false
        if (evidenceNavigationError.value) {
          await nextTick()
          if (current()) document.getElementById('evidence-navigation')?.focus()
        }
      }
    }
  }

  onScopeDispose(clearEvidenceNavigation)
  return { evidenceTarget, evidenceNavigationLoading, evidenceNavigationError, clearEvidenceNavigation, openEvidence }
}
