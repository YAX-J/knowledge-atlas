import { nextTick, onScopeDispose, reactive, ref, type Ref } from 'vue'
import { getEntityDetail, getKnowledgeHistory, inspectGovernance, listKnowledgeChanges, proposeKnowledgeChange, resolveKnowledgeChange } from '../api/knowledgeAtlas'
import type { EntityDetail, GovernanceKind, GovernanceResult, KnowledgeChangeInput, KnowledgeChangeList, KnowledgeHistory } from '../types'
import { useLatestRequest } from './useLatestRequest'

interface Context { projectId: string | undefined; entityId: string | undefined; active: boolean; validAt: string }
interface Effects { clearSearch: () => void; loadRealGraph: (center: string) => Promise<void>; selectEntityId: (id: string) => void }

export function useKnowledgeEvolution(context: () => Context, busy: Ref<boolean>, effects: Effects, errorMessage: (error: unknown) => string) {
  let disposed = false, generation = 0
  const current = (id: string, captured: number) => !disposed && generation === captured && context().projectId === id && context().active
  const history = ref<KnowledgeHistory | null>(null)
  const knowledgeChanges = ref<KnowledgeChangeList | null>(null)
  const governance = ref<GovernanceResult | null>(null)
  const governanceKind = ref<GovernanceKind | ''>('')
  const comparisonState = useLatestRequest<EntityDetail[]>(errorMessage)
  const { result: comparison, loading: comparisonLoading, error: comparisonError } = comparisonState
  let comparisonIds: string[] = []
  function closeComparison() { comparisonState.clear(); comparisonIds = [] }
  async function compareKnowledge(ids = comparisonIds) {
    const projectId = context().projectId
    const unique = [...new Set(ids)]
    if (!projectId || busy.value || unique.length !== 2) return
    comparisonIds = unique
    await comparisonState.run(async () => {
      const details = await Promise.all(unique.map(id => getEntityDetail(id)))
      if (details.some((detail, index) => detail.entity.project_id !== projectId || detail.entity.id !== unique[index])) {
        throw new Error('Comparison context changed')
      }
      return details
    }, () => context().projectId === projectId && context().active)
    await nextTick()
    if (context().projectId === projectId && comparison.value?.every((detail, index) => detail.entity.id === unique[index])) {
      const panel = document.getElementById('knowledge-comparison')
      panel?.focus({ preventScroll: true }); panel?.scrollIntoView({ block: 'nearest', behavior: 'instant' })
    }
  }
  const evolutionLoading = reactive({ history: false, changes: false, governance: false })
  const evolutionError = reactive({ history: '', changes: '', governance: '', action: '' })
  const changeNotice = ref('')
  let historyRequest = 0
  let changesRequest = 0
  let governanceRequest = 0

  function clearEvolution() {
    generation++
    historyRequest++; changesRequest++; governanceRequest++
    history.value = null; knowledgeChanges.value = null; governance.value = null
    evolutionLoading.history = evolutionLoading.changes = evolutionLoading.governance = false
    evolutionError.history = evolutionError.changes = evolutionError.governance = evolutionError.action = ''
    changeNotice.value = ''
    closeComparison(); governanceKind.value = ''
  }

  async function loadHistory() {
    if (disposed) return
    const projectId = context().projectId, entityId = context().entityId
    const request = ++historyRequest
    history.value = null; evolutionError.history = ''
    if (!projectId || !entityId) { evolutionLoading.history = false; return }
    evolutionLoading.history = true
    try {
      const result = await getKnowledgeHistory(projectId, entityId)
      if (request === historyRequest && context().projectId === projectId) history.value = result
    } catch (error) { if (request === historyRequest) evolutionError.history = errorMessage(error) }
    finally { if (request === historyRequest) evolutionLoading.history = false }
  }

  async function loadChanges(page = 1) {
    if (disposed) return
    const projectId = context().projectId
    if (!projectId) return
    const request = ++changesRequest
    evolutionLoading.changes = true; evolutionError.changes = ''
    try {
      const result = await listKnowledgeChanges(projectId, page)
      if (request === changesRequest && context().projectId === projectId) knowledgeChanges.value = result
    } catch (error) { if (request === changesRequest) evolutionError.changes = errorMessage(error) }
    finally { if (request === changesRequest) evolutionLoading.changes = false }
  }

  async function runGovernance(kind = governanceKind.value) {
    if (disposed) return
    const projectId = context().projectId
    if (!projectId || busy.value) return
    const request = ++governanceRequest
    governanceKind.value = kind
    closeComparison()
    governance.value = null; evolutionLoading.governance = true; evolutionError.governance = ''
    try {
      const result = await inspectGovernance(projectId, kind)
      if (request === governanceRequest && context().projectId === projectId) governance.value = result
    } catch (error) { if (request === governanceRequest) evolutionError.governance = errorMessage(error) }
    finally { if (request === governanceRequest) evolutionLoading.governance = false }
  }

  async function proposeChange(input: KnowledgeChangeInput) {
    const projectId = context().projectId
    const captured = generation
    if (!projectId || !context().active || disposed || busy.value || context().validAt) return
    busy.value = true; evolutionError.action = ''; changeNotice.value = ''
    try {
      await proposeKnowledgeChange(projectId, input)
      if (!current(projectId, captured)) return
      changeNotice.value = '建议已保存，尚未改变正式知识。请核对原文后单独确认。'
      await loadChanges(1)
    } catch (error) { if (current(projectId, captured)) evolutionError.action = errorMessage(error) }
    finally { busy.value = false }
  }

  async function resolveChange(id: string, action: 'confirm' | 'reject') {
    const projectId = context().projectId
    const captured = generation
    if (!projectId || !context().active || disposed || busy.value || context().validAt) return
    busy.value = true; evolutionError.action = ''; changeNotice.value = ''
    try {
      const result = await resolveKnowledgeChange(projectId, id, action)
      if (!current(projectId, captured)) return
      changeNotice.value = action === 'reject' ? '建议已拒绝，知识保持不变。' : '建议已确认，审核前后快照已保存。'
      effects.clearSearch()
      governanceRequest++; governance.value = null; evolutionLoading.governance = false
      closeComparison()
      if (action === 'confirm' && result.kind === 'SUPERSEDES') effects.selectEntityId(result.new_entity_id)
      await Promise.all([loadChanges(knowledgeChanges.value?.page ?? 1), effects.loadRealGraph('')])
    } catch (error) { if (current(projectId, captured)) evolutionError.action = errorMessage(error) }
    finally { busy.value = false }
  }


  function clearHistory() { historyRequest++; history.value = null; evolutionLoading.history = false; evolutionError.history = '' }
  function clearGovernance() { governanceRequest++; governance.value = null; evolutionLoading.governance = false }

  onScopeDispose(() => { disposed = true; clearEvolution() })
  return { history, knowledgeChanges, governance, governanceKind, comparison, comparisonLoading, comparisonError, closeComparison, compareKnowledge, evolutionLoading, evolutionError, changeNotice, clearEvolution, clearHistory, clearGovernance, loadHistory, loadChanges, runGovernance, proposeChange, resolveChange }
}
