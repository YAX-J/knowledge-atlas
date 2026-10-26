import { onScopeDispose, ref, watch, type Ref } from 'vue'
import { listKnowledgeRetirements, retireKnowledge } from '../api/knowledgeAtlas'
import type { RetirementInput, RetirementList } from '../types'
import { useLatestRequest } from './useLatestRequest'

interface Context { projectId: string | undefined; active: boolean; validAt: string }

export function useKnowledgeRetirement(context: () => Context, busy: Ref<boolean>, describeError: (error: unknown) => string,
  onRetired: () => Promise<void>) {
  const records = useLatestRequest<RetirementList>(describeError)
  const actionError = ref(''), notice = ref('')
  let generation = 0, disposed = false
  let submission: (RetirementInput & { request_id: string }) | null = null
  const current = (id: string, captured: number) => !disposed && generation === captured && context().projectId === id && context().active

  async function load(page = 1) {
    const { projectId, active } = context()
    const captured = generation
    if (!projectId || !active || disposed) return
    await records.run(() => listKnowledgeRetirements(projectId, page), () => current(projectId, captured))
  }

  async function retire(input: RetirementInput) {
    const { projectId, active, validAt } = context()
    if (!projectId || !active || validAt || busy.value || disposed) return
    const captured = generation
    const previous = submission && { kind: submission.kind, knowledge_id: submission.knowledge_id,
      category: submission.category, reason: submission.reason }
    if (JSON.stringify(previous) !== JSON.stringify(input)) submission = { ...input, request_id: crypto.randomUUID() }
    busy.value = true
    actionError.value = notice.value = ''
    try {
      await retireKnowledge(projectId, submission!)
      if (!current(projectId, captured)) return
      submission = null
      notice.value = '已停用并保存审计快照。当前查询不再使用此项，历史与原文仍保留。'
      await Promise.all([load(1), onRetired()])
    } catch (error) {
      if (current(projectId, captured)) actionError.value = describeError(error)
    } finally { busy.value = false }
  }

  watch(() => [context().projectId, context().active], () => {
    generation++; records.clear(); actionError.value = notice.value = ''; submission = null
    if (context().active) void load()
  }, { flush: 'sync' })
  onScopeDispose(() => { disposed = true; generation++; records.clear() })
  return { retirements: records.result, retirementsLoading: records.loading, retirementsError: records.error,
    retirementError: actionError, retirementNotice: notice, loadRetirements: load, retireKnowledge: retire }
}
