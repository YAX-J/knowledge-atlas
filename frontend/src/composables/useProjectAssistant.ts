import { computed, onScopeDispose, ref, watch } from 'vue'
import { ApiError } from '../api/client'
import { getAssistantTask, listAssistantTasks, startAssistantTask, type AssistantInput, type AssistantSummary, type AssistantTask } from '../api/assistant'
import type { Page } from '../types'

export function useProjectAssistant(projectId: () => string | undefined) {
  const history = ref<Page<AssistantSummary> | null>(null), selected = ref<AssistantTask | null>(null)
  const loading = ref(false), sending = ref(false), unknown = ref(false), error = ref('')
  let generation = 0, reads = 0, disposed = false
  let pending: AssistantInput | null = null, selectedId: string | null = null
  const key = (id: string) => `ka-project-assistant:${id}`
  const current = (id: string, version: number) => !disposed && generation === version && projectId() === id
  const busy = computed(() => sending.value || unknown.value || selected.value?.status === 'running')
  function save(id: string) {
    try { sessionStorage.setItem(key(id), JSON.stringify({pending, selectedId})) } catch { /* Memory remains usable. */ }
  }
  const describe = (cause: unknown) => cause instanceof Error ? cause.message : '助手任务读取失败，请重试。'
  async function refresh(page = history.value?.page ?? 1) {
    const project = projectId(), version = generation, read = ++reads
    if (!project || disposed) return
    loading.value = true; error.value = ''
    const id = pending?.request_id ?? selectedId
    try {
      const rows = await listAssistantTasks(project, page)
      const detail = id ? await getAssistantTask(project, id) : null
      if (!current(project, version) || read !== reads) return
      history.value = rows; selected.value = detail
      if (detail) { selectedId = detail.id; pending = null; unknown.value = false; save(project) }
    } catch (cause) {
      if (current(project, version) && read === reads) error.value = describe(cause)
    } finally { if (current(project, version) && read === reads) loading.value = false }
  }
  async function select(id: string) {
    if (sending.value || unknown.value) return
    selectedId = id
    const project = projectId()
    if (project) save(project)
    selected.value = null
    await refresh()
  }
  async function submit(input: Omit<AssistantInput, 'request_id'>, retry = false) {
    const project = projectId(), version = generation
    if (!project || disposed || sending.value || selected.value?.status === 'running' || unknown.value && !retry) return
    if (!retry) pending = {...input, request_id: crypto.randomUUID()}
    if (!pending) return
    selectedId = pending.request_id; save(project); sending.value = true; loading.value = false; error.value = ''; ++reads
    try {
      const result = await startAssistantTask(project, pending)
      if (!current(project, version)) return
      selected.value = result; pending = null; unknown.value = false; save(project)
      await refresh(1)
    } catch (cause) {
      if (!current(project, version)) return
      error.value = describe(cause)
      unknown.value = !(cause instanceof ApiError && cause.status >= 400 && cause.status < 500)
      if (!unknown.value) { pending = null; selectedId = selected.value?.id ?? null; save(project) }
    } finally { if (current(project, version)) sending.value = false }
  }
  watch(projectId, () => {
    generation++; reads++; pending = null; selectedId = null
    history.value = null; selected.value = null; loading.value = sending.value = unknown.value = false; error.value = ''
    const project = projectId()
    if (!project) return
    try {
      const saved = JSON.parse(sessionStorage.getItem(key(project)) ?? 'null') as {pending?: AssistantInput; selectedId?: string} | null
      if (typeof saved?.selectedId === 'string') selectedId = saved.selectedId
      if (saved?.pending && typeof saved.pending.request_id === 'string' && typeof saved.pending.goal === 'string' && Array.isArray(saved.pending.source_ids)) {
        pending = saved.pending; unknown.value = true
      }
    } catch { /* Ignore malformed local state. */ }
    void refresh(1)
  }, {immediate: true, flush: 'sync'})
  const timer = setInterval(() => { if (selected.value?.status === 'running' && !loading.value && !sending.value) void refresh() }, 3000)
  onScopeDispose(() => { disposed = true; generation++; reads++; clearInterval(timer) })
  return {history, selected, loading, sending, unknown, error, busy, refresh, select, submit,
    retry: () => pending ? submit(pending, true) : Promise.resolve()}
}
