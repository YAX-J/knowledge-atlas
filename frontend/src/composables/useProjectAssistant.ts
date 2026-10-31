import { computed, onScopeDispose, ref, watch } from 'vue'
import { ApiError } from '../api/client'
import { approveAssistantOperation, cancelAssistantTask, continueAssistantTask, getAssistantTask, listAssistantTasks, startAssistantTask, type AssistantApproval, type AssistantOperation, type AssistantContinue, type AssistantInput, type AssistantSummary, type AssistantTask } from '../api/assistant'
import type { Page } from '../types'

export function useProjectAssistant(projectId: () => string | undefined) {
  const history = ref<Page<AssistantSummary> | null>(null), selected = ref<AssistantTask | null>(null)
  const loading = ref(false), sending = ref(false), unknown = ref(false), error = ref('')
  let generation = 0, reads = 0, disposed = false
  let pending: AssistantInput | null = null, selectedId: string | null = null
  let pendingContinue: {taskId: string; input: AssistantContinue} | null = null
  let pendingApproval: {taskId:string;input:AssistantApproval}|null=null
  const approvalUnknown=ref(false)
  const key = (id: string) => `ka-project-assistant:${id}`
  const current = (id: string, version: number) => !disposed && generation === version && projectId() === id
  const active = () => selected.value?.status === 'running' || selected.value?.status === 'queued'
  const busy = computed(() => sending.value || unknown.value || active())
  function save(id: string) {
    try { sessionStorage.setItem(key(id), JSON.stringify({pending, selectedId, pendingContinue, pendingApproval})) } catch { /* Memory remains usable. */ }
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
      if(detail&&pendingApproval?.taskId===detail.id&&detail.operations?.some(o=>o.id===pendingApproval!.input.operation_id&&o.status!=='pending')){pendingApproval=null;approvalUnknown.value=false}
      if (detail && pendingContinue?.taskId === detail.id && (detail.revision ?? 0) > pendingContinue.input.expected_revision) pendingContinue = null
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
    if (!project || disposed || sending.value || active() || unknown.value && !retry) return
    if (!retry) {pending = {...input, protocol: input.protocol??'assistant-task-v2', request_id: crypto.randomUUID()}; pendingContinue = null;pendingApproval=null;approvalUnknown.value=false}
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
  async function approve(operation:AssistantOperation,decision:'approve'|'reject') {
    const project=projectId(),task=selected.value,version=generation
    if(!project||!task||sending.value||approvalUnknown.value&&!pendingApproval||disposed)return
    if(pendingApproval&&(pendingApproval.taskId!==task.id||pendingApproval.input.operation_id!==operation.id||pendingApproval.input.decision!==decision))return
    if(!pendingApproval)pendingApproval={taskId:task.id,input:{request_id:crypto.randomUUID(),operation_id:operation.id,proposal_sha256:operation.proposal_sha256,decision}}
    save(project);sending.value=true;error.value='';++reads
    try{const result=await approveAssistantOperation(project,task.id,pendingApproval.input);if(!current(project,version))return;selected.value=result;pendingApproval=null;approvalUnknown.value=false;save(project);await refresh()}
    catch(cause){if(current(project,version)){error.value=describe(cause);approvalUnknown.value=!(cause instanceof ApiError&&cause.status>=400&&cause.status<500);if(!approvalUnknown.value)pendingApproval=null;save(project)}}
    finally{if(current(project,version))sending.value=false}
  }
  function retryApproval(){const op=selected.value?.operations?.find(o=>o.id===pendingApproval?.input.operation_id);return op&&pendingApproval?approve(op,pendingApproval.input.decision):Promise.resolve()}
  async function control(kind: 'cancel' | 'continue', acknowledgeUnknown = false) {
    const project = projectId(), value = selected.value, version = generation
    if (!project || !value || sending.value || unknown.value || disposed) return
    sending.value = true; loading.value = false; ++reads; error.value = ''
    try {
      if (kind === 'continue' && (!pendingContinue || pendingContinue.taskId !== value.id)) {
        pendingContinue = {taskId: value.id, input: {request_id: crypto.randomUUID(), expected_revision: value.revision ?? 0,
          checkpoint_id: value.checkpoint_id ?? null, acknowledge_unknown: acknowledgeUnknown}}
        save(project)
      }
      const result = kind === 'cancel' ? await cancelAssistantTask(project, value.id)
        : await continueAssistantTask(project, value.id, pendingContinue!.input)
      if (!current(project, version)) return
      selected.value = result; pendingContinue = null; save(project)
      await refresh()
    } catch (cause) {
      if (!current(project, version)) return
      if (cause instanceof ApiError && cause.status >= 400 && cause.status < 500) {pendingContinue = null; save(project)}
      error.value = describe(cause)
      // Never automatically repeat a control POST after an unknown transport result.
    } finally {if (current(project, version)) sending.value = false}
  }
  watch(projectId, () => {
    generation++; reads++; pending = null; selectedId = null; pendingContinue = null;pendingApproval=null;approvalUnknown.value=false
    history.value = null; selected.value = null; loading.value = sending.value = unknown.value = false; error.value = ''
    const project = projectId()
    if (!project) return
    try {
      const saved = JSON.parse(sessionStorage.getItem(key(project)) ?? 'null') as {pending?: AssistantInput; selectedId?: string; pendingContinue?: {taskId: string; input: AssistantContinue};pendingApproval?:{taskId:string;input:AssistantApproval}} | null
      if (typeof saved?.selectedId === 'string') selectedId = saved.selectedId
      if(saved?.pendingApproval&&typeof saved.pendingApproval.input?.request_id==='string'){pendingApproval=saved.pendingApproval;approvalUnknown.value=true}
      if (saved?.pendingContinue && typeof saved.pendingContinue.taskId === 'string' && typeof saved.pendingContinue.input?.request_id === 'string') pendingContinue = saved.pendingContinue
      if (saved?.pending && typeof saved.pending.request_id === 'string' && typeof saved.pending.goal === 'string' && Array.isArray(saved.pending.source_ids)) {
        pending = saved.pending; unknown.value = true
      }
    } catch { /* Ignore malformed local state. */ }
    void refresh(1)
  }, {immediate: true, flush: 'sync'})
  const timer = setInterval(() => { if (active() && !loading.value && !sending.value) void refresh() }, 3000)
  onScopeDispose(() => { disposed = true; generation++; reads++; clearInterval(timer) })
  return {history, selected, loading, sending, unknown, error, busy, refresh, select, submit, approve, approvalUnknown, retryApproval,
    retry: () => pending ? submit(pending, true) : Promise.resolve(), cancel: () => control('cancel'),
    resume: (acknowledgeUnknown = false) => control('continue', acknowledgeUnknown)}
}
