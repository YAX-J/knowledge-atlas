import { onScopeDispose, ref, watch, type Ref } from 'vue'
import { getIdentity, listOperations, operateKnowledge, proposeEvolutionGroup } from '../api/workspace'
import type { IdentityInfo, KnowledgeOperation, ManagementIntent, Page } from '../types'

export function useKnowledgeManagement(context: () => { projectId?: string; entityId?: string; active: boolean; validAt: string },
  busy: Ref<boolean>, afterChange: () => Promise<void>) {
  const identity = ref<IdentityInfo | null>(null)
  const operations = ref<Page<KnowledgeOperation> | null>(null)
  const loading = ref(false)
  const error = ref('')
  const notice = ref('')
  let reads = 0, generation = 0, disposed = false
  let submission: { signature: string; id: string } | null = null
  async function refresh(page = 1) {
    const captured = context(), request = ++reads, capturedGeneration = generation
    if (!captured.projectId || !captured.active) return
    loading.value = true; error.value = ''
    try {
      const [history, info] = await Promise.all([listOperations(captured.projectId, page), captured.entityId ? getIdentity(captured.projectId, captured.entityId, captured.validAt) : Promise.resolve(null)])
      if (disposed || request !== reads || capturedGeneration !== generation) return
      operations.value = history; identity.value = info
    } catch (value) { if (!disposed && request === reads && capturedGeneration === generation) error.value = value instanceof Error ? value.message : '读取失败，请重试。' }
    finally { if (!disposed && request === reads && capturedGeneration === generation) loading.value = false }
  }
  async function apply(input: ManagementIntent) {
    const captured = context(), capturedGeneration = generation
    if (!captured.projectId || !captured.active || captured.validAt || busy.value) return
    const signature = JSON.stringify([captured.projectId, input])
    if (submission?.signature !== signature) submission = { signature, id: crypto.randomUUID() }
    busy.value = true; error.value = ''; notice.value = ''
    try {
      if (input.action === 'evolution_group') await proposeEvolutionGroup(captured.projectId, { ...input, request_id: submission.id })
      else await operateKnowledge(captured.projectId, { ...input, request_id: submission.id })
      if (disposed || capturedGeneration !== generation) return
      submission = null
      notice.value = '操作已记录，原始知识和历史证据继续保留。'
      await afterChange()
      await refresh()
    } catch (value) { if (!disposed && capturedGeneration === generation) error.value = value instanceof Error ? value.message : '未能确认处理结果，请刷新记录后重试。' }
    finally { busy.value = false }
  }
  watch(() => [context().projectId, context().entityId, context().active, context().validAt] as const, () => {
    generation++; reads++; identity.value = null; operations.value = null; error.value = notice.value = ''; loading.value = false
    if (context().active && context().projectId) void refresh()
  }, { flush: 'sync', immediate: true })
  onScopeDispose(() => { disposed = true; generation++; reads++ })
  return { identity, operations, loading, error, notice, refresh, apply }
}
