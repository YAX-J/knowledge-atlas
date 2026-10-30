import { computed, ref, watch } from 'vue'
import { getCodeAnalysisContexts, type CodeAnalysisContexts, type CodeAnalysisSelection } from '../api/knowledgeAtlas'
import { useLatestRequest } from './useLatestRequest'

/** Read-only version choices are scoped separately from paid workflow submission. */
export function useCodeContextSelection(
  projectId: () => string | undefined,
  sourceId: () => string | undefined,
  enabled: () => boolean,
) {
  const read = useLatestRequest<CodeAnalysisContexts>(cause => cause instanceof Error ? cause.message : '读取代码版本失败，请重试。')
  const snapshotId = ref('')
  const versions = ref<Record<string, string>>({})
  watch(read.result, value => {
    snapshotId.value = value?.default_snapshot_id ?? ''
    versions.value = Object.fromEntries((value?.version_groups ?? []).map(group => [group.path, '']))
  }, { flush: 'sync' })

  async function refresh() {
    const project = projectId(), source = sourceId()
    if (!project || !source || !enabled()) return
    await read.run(() => getCodeAnalysisContexts(source),
      () => enabled() && projectId() === project && sourceId() === source)
  }
  watch([projectId, sourceId, enabled], () => {
    read.clear()
    snapshotId.value = ''
    versions.value = {}
    if (enabled()) void refresh()
  }, { immediate: true, flush: 'sync' })

  const validationError = computed(() => {
    const contexts = read.result.value
    if (!contexts) return ''
    if (contexts.snapshots.length) {
      return contexts.snapshots.some(item => item.id === snapshotId.value) ? '' : '请选择当前资料对应的提交快照。'
    }
    const selected = Object.entries(versions.value).filter(([, identifier]) => identifier)
    if (selected.length > 99) return '最多可指定 99 个相关文件版本，请将其余文件改为自动选择。'
    if (selected.some(([path, identifier]) => !contexts.version_groups.some(group => group.path === path &&
      group.versions.some(item => item.id === identifier)))) return '部分版本已不在当前选择范围，请重新读取代码版本。'
    return ''
  })
  const ready = computed(() => !!read.result.value && !read.loading.value && !read.error.value && !validationError.value)
  const selection = computed<CodeAnalysisSelection>(() => snapshotId.value
    ? { snapshotId: snapshotId.value }
    : { versionIds: Object.values(versions.value).filter(Boolean) })
  return { contexts: read.result, loading: read.loading, error: read.error, snapshotId, versions,
    validationError, ready, selection, refresh }
}
