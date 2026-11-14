import { computed, onScopeDispose, ref, watch } from 'vue'
import { askConversation, createConversation, listConversations, listConversationTurns } from '../api/workspace'
import type { Conversation, ConversationTurn, Page, QuestionAnswer, QuestionRetrievalMode } from '../types'

export function useConversations(projectId: () => string | undefined) {
  const conversations = ref<Page<Conversation> | null>(null)
  const turns = ref<Page<ConversationTurn> | null>(null)
  const selectedId = ref('')
  const result = ref<QuestionAnswer | null>(null)
  const loading = ref(false)
  const sending = ref(false)
  const error = ref('')
  const unknown = ref(false)
  const retryTurn = ref<ConversationTurn | null>(null)
  let pendingRequest: ConversationTurn | null = null
  const pendingKey = (project: string, conversation: string) => `ka-pending-turn:${project}:${conversation}`
  function storePending(project: string, conversation: string) {
    try {
      if (pendingRequest) sessionStorage.setItem(pendingKey(project, conversation), JSON.stringify(pendingRequest))
      else sessionStorage.removeItem(pendingKey(project, conversation))
    } catch { /* Browser storage can be disabled; in-memory idempotency still applies. */ }
  }
  function restorePending(project: string, conversation: string) {
    try {
      const value = JSON.parse(sessionStorage.getItem(pendingKey(project, conversation)) ?? 'null') as ConversationTurn | null
      pendingRequest = value?.status === 'interrupted' && typeof value.request_id === 'string' && typeof value.question === 'string' ? value : null
    } catch { pendingRequest = null }
  }
  let generation = 0, reads = 0, disposed = false
  const current = (project: string, captured: number) => !disposed && captured === generation && projectId() === project
  const busy = computed(() => sending.value || !!turns.value?.items.some(item => item.status === 'running'))
  const describe = (value: unknown) => value instanceof Error ? value.message : '读取失败，请重试。'

  async function refresh(page = conversations.value?.page ?? 1, turnPage = turns.value?.page ?? 1) {
    const project = projectId(), captured = generation, request = ++reads, selected = selectedId.value
    if (!project) return
    loading.value = true
    error.value = ''
    try {
      const [list, initialHistory] = await Promise.all([listConversations(project, page), selected ? listConversationTurns(project, selected, turnPage) : Promise.resolve(null)])
      let history = initialHistory
      // A delayed request may not yet have appeared in the requested history page.
      if (pendingRequest && selected && history && !history.items.some(item => item.request_id === pendingRequest?.request_id)) {
        const lastPage = Math.max(1, Math.ceil(history.total / history.page_size))
        if (lastPage !== history.page) history = await listConversationTurns(project, selected, lastPage)
      }
      if (!current(project, captured) || request !== reads || selectedId.value !== selected) return
      conversations.value = list
      turns.value = history
      retryTurn.value = [...(history?.items ?? [])].reverse().find(item => ['failed', 'interrupted'].includes(item.status)) ?? null
      if (pendingRequest) {
        const saved = history?.items.find(item => item.request_id === pendingRequest?.request_id)
        if (saved?.status === 'succeeded') { pendingRequest = null; storePending(project, selected) }
        else if (!saved || ['failed', 'interrupted'].includes(saved.status)) retryTurn.value = saved ?? pendingRequest
      }
      if (history?.items.length) result.value = [...history.items].reverse().find(item => item.answer)?.answer ?? null
      unknown.value = false
    } catch (value) {
      if (current(project, captured) && request === reads) error.value = describe(value)
    } finally {
      if (current(project, captured) && request === reads) loading.value = false
    }
  }

  async function select(id: string) {
    if (sending.value) return
    generation++; reads++; pendingRequest = null
    selectedId.value = id
    if (projectId()) restorePending(projectId()!, id)
    result.value = null; turns.value = null; retryTurn.value = null; unknown.value = false
    await refresh(conversations.value?.page ?? 1, 1)
  }

  async function start() {
    const project = projectId(), captured = generation
    if (!project || sending.value || loading.value) return
    loading.value = true; error.value = ''
    try {
      const created = await createConversation(project)
      if (!current(project, captured)) return
      selectedId.value = created.id; turns.value = null; result.value = null
      pendingRequest = null; retryTurn.value = null; unknown.value = false
      loading.value = false
      await refresh(1, 1)
    } catch (value) {
      if (current(project, captured)) error.value = describe(value)
    } finally { if (current(project, captured)) loading.value = false }
  }

  async function send(question: string, mode: QuestionRetrievalMode, retry?: ConversationTurn, validAt?: string) {
    const project = projectId(), captured = generation
    if (!project || sending.value || loading.value || busy.value || unknown.value || pendingRequest && !retry) return
    sending.value = true; error.value = ''
    try {
      if (!selectedId.value) {
        const created = await createConversation(project)
        if (!current(project, captured)) return
        selectedId.value = created.id
      }
      const conversation = selectedId.value
      const requestId = retry?.request_id ?? crypto.randomUUID()
      const requestTime = retry ? retry.valid_at : validAt
      pendingRequest = { id: requestId, request_id: requestId, question, retrieval_mode: mode, valid_at: requestTime ?? null,
        position: retry?.position ?? 0, status: 'interrupted', answer: null, error_code: null, created_at: new Date().toISOString() }
      storePending(project, conversation)
      const response = await askConversation(project, conversation, {
        request_id: requestId, question, retrieval_mode: mode, ...(requestTime ? { valid_at: requestTime } : {}),
        ...(retry ? { retry_interrupted: true } : {}),
      })
      if (!current(project, captured) || selectedId.value !== conversation) return
      result.value = response.answer; retryTurn.value = null; pendingRequest = null
      storePending(project, conversation)
      const page = Math.ceil(response.position / 20)
      await refresh(1, page)
    } catch (value) {
      if (current(project, captured)) {
        error.value = describe(value)
        unknown.value = true // Inspect persisted state before offering another paid request.
      }
    } finally { if (current(project, captured)) sending.value = false }
  }

  watch(projectId, () => {
    generation++; reads++
    conversations.value = turns.value = null; selectedId.value = ''; result.value = null
    error.value = ''; loading.value = sending.value = unknown.value = false; retryTurn.value = null
    pendingRequest = null
    if (projectId()) void refresh(1, 1)
  }, { immediate: true, flush: 'sync' })
  onScopeDispose(() => { disposed = true; generation++; reads++ })
  return { conversations, turns, selectedId, result, loading, sending, busy, error, unknown, retryTurn, refresh, select, start, send }
}
