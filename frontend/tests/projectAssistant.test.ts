import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { effectScope, ref } from 'vue'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import * as api from '../src/api/assistant'
import { ApiError } from '../src/api/client'
import { getCodeAnalysisContexts, listRepositories, listSources } from '../src/api/knowledgeAtlas'
import { useProjectAssistant } from '../src/composables/useProjectAssistant'
import ProjectAssistantPanel from '../src/components/agent/ProjectAssistantPanel.vue'
import { project, source } from './fixtures'

vi.mock('../src/api/assistant')
vi.mock('../src/api/knowledgeAtlas', () => ({listSources: vi.fn(), listRepositories: vi.fn(), getCodeAnalysisContexts: vi.fn()}))
enableAutoUnmount(afterEach)
const task: api.AssistantTask = {
  id: 'assistant-1', project_id: project.id, goal: 'Explain project modules', status: 'succeeded',
  created_at: project.created_at, updated_at: project.updated_at, error_code: null,
  scope: {source_ids: [source.id], snapshot_id: null, commit_sha: null, valid_at: null},
  usage: {model: 2, tool: 2, embedding: 0, limits: {model: 8, tool: 16, embedding: 0}}, events: [],
  result: {protocol: 'assistant-report-v1', action: 'finish', question: null,
    report: {title: 'Project modules', claims: [{text: '<script>Storage</script>', status: 'referenced', reference_ids: ['ref-1']}], missing_information: ['No performance results.']},
    references: [{id: 'ref-1', kind: 'code', source_id: source.id, chunk_id: 'chunk-1', evidence_id: null,
      source_sha256: source.content_sha256, path: 'src/main.py', start_line: 1, end_line: 2, quote: 'def store():\n    return 1', snapshot_id: null, commit_sha: null}]},
}
const summary = () => {const {result: _result, usage: _usage, events: _events, scope: _scope, ...row} = task; return row}
beforeEach(() => {
  vi.resetAllMocks(); sessionStorage.clear()
  vi.mocked(api.listAssistantTasks).mockResolvedValue({items: [], total: 0, page: 1, page_size: 10})
  vi.mocked(api.getAssistantTask).mockResolvedValue(task)
  vi.mocked(api.startAssistantTask).mockResolvedValue(task)
  vi.mocked(listSources).mockResolvedValue({items: [{...source, task_id: null, task_status: null}], total: 1, page: 1, page_size: 20})
  vi.mocked(getCodeAnalysisContexts).mockResolvedValue({default_snapshot_id: null, snapshots: [], version_groups: [], truncated: false})
})

it('submits a goal with explicit source versions and displays typed citations as escaped text', async () => {
  const wrapper = mount(ProjectAssistantPanel, {props: {projectId: project.id}})
  await flushPromises()
  await wrapper.get('textarea').setValue('Explain project modules')
  await wrapper.get('.assistant-sources input[type=checkbox]').setValue(true); await flushPromises()
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(api.startAssistantTask).toHaveBeenCalledOnce()
  expect(vi.mocked(api.startAssistantTask).mock.calls[0]![1]).toMatchObject({goal: task.goal, source_ids: [source.id]})
  expect(vi.mocked(api.startAssistantTask).mock.calls[0]![1].protocol).toBe('assistant-task-v3')
  expect(wrapper.get('[aria-label="项目引用报告"]').text()).toContain('<script>Storage</script>')
  expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.text()).toContain('源码 / 派生结构')
  await wrapper.findAll('button').find(item => item.text() === '查看引用 1')!.trigger('click')
  expect(wrapper.emitted('openEvidence')).toEqual([[{source_id: source.id, chunk_id: 'chunk-1'}]])
  expect(wrapper.text()).toContain('No performance results.')
})

it('starts a repository job and renders checkpointed counts after remount without submitting again', async () => {
  vi.mocked(listRepositories).mockResolvedValue({ items: [{ id: 'repo', project_id: project.id, name: 'example/demo',
    kind: 'git_remote', provider: 'github', remote_owner: 'example', remote_name: 'demo', remote_url: null,
    provider_repository_id: null, created_at: project.created_at, updated_at: project.updated_at }], total: 1, page: 1, page_size: 20 })
  const prepared: api.AssistantTask = { ...task, scope: { ...task.scope, source_ids: [], repository_progress: {
    phase: 'reporting', snapshot_id: 'snapshot', commit_sha: 'a'.repeat(40), ref: 'test',
    completed_files: 75, total_files: 75, pending_directories: 0, parsed_files: 74, failed_files: 0, skipped_files: 1,
  } } }
  vi.mocked(api.startAssistantTask).mockResolvedValue(prepared)
  vi.mocked(api.getAssistantTask).mockResolvedValue(prepared)
  const wrapper = mount(ProjectAssistantPanel, { props: { projectId: project.id } })
  await flushPromises()
  await wrapper.get('textarea').setValue('生成仓库说明')
  await wrapper.get('fieldset > label input[type=checkbox]').setValue(true)
  await flushPromises()
  await wrapper.get('input[placeholder="留空使用默认分支"]').setValue('test')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(api.startAssistantTask).toHaveBeenCalledWith(project.id, expect.objectContaining({ whole_repository: true,
    repository_id: 'repo', repository_ref: 'test', allowed_actions: ['import_repository_snapshot'], source_ids: [] }))
  expect(wrapper.text()).toContain('75 / 75')
  expect(wrapper.text()).toContain('已解析 74')
  wrapper.unmount()
  const restored = mount(ProjectAssistantPanel, { props: { projectId: project.id } })
  await flushPromises()
  expect(restored.text()).toContain('test @ aaaaaaaaaaaa')
  expect(api.startAssistantTask).toHaveBeenCalledOnce()
})

it('restores saved task IDs and history through GET without replaying submissions', async () => {
  sessionStorage.setItem(`ka-project-assistant:${project.id}`, JSON.stringify({selectedId: task.id, pending: null}))
  vi.mocked(api.listAssistantTasks).mockResolvedValue({items: [summary()], total: 1, page: 1, page_size: 10})
  const wrapper = mount(ProjectAssistantPanel, {props: {projectId: project.id}}); await flushPromises()
  expect(api.getAssistantTask).toHaveBeenCalledWith(project.id, task.id)
  expect(wrapper.text()).toContain('精确来源 UUID')
  expect(api.startAssistantTask).not.toHaveBeenCalled()
})

it('preserves unknown request UUIDs on reload and requires an explicit retry after a failed read', async () => {
  vi.mocked(api.startAssistantTask).mockRejectedValueOnce(new ApiError(0, {error: {message: 'Unknown transport outcome'}}))
  const wrapper = mount(ProjectAssistantPanel, {props: {projectId: project.id}}); await flushPromises()
  await wrapper.get('textarea').setValue('Explain project modules')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  const body = vi.mocked(api.startAssistantTask).mock.calls[0]![1]
  expect(wrapper.text()).toContain('提交结果尚未确认')
  wrapper.unmount()
  vi.mocked(api.getAssistantTask).mockRejectedValueOnce(new ApiError(404, {error: {message: 'Not stored yet'}}))
  const restored = mount(ProjectAssistantPanel, {props: {projectId: project.id}}); await flushPromises()
  expect(api.startAssistantTask).toHaveBeenCalledOnce()
  expect(restored.get('fieldset').attributes('disabled')).toBeDefined()
  await restored.findAll('button').find(item => item.text() === '重发同一助手任务')!.trigger('click'); await flushPromises()
  expect(vi.mocked(api.startAssistantTask).mock.calls[1]![1]).toEqual(body)
})

it('discards delayed task results from another project', async () => {
  const id = ref<string | undefined>(project.id), scope = effectScope()
  let resolve!: (value: api.AssistantTask) => void
  vi.mocked(api.startAssistantTask).mockImplementationOnce(() => new Promise(done => {resolve = done}))
  const assistant = scope.run(() => useProjectAssistant(() => id.value))!
  await flushPromises()
  const submitting = assistant.submit({goal: task.goal, source_ids: []})
  id.value = 'project-2'; await flushPromises()
  resolve(task); await submitting
  expect(assistant.selected.value).toBeNull()
  expect(assistant.sending.value).toBe(false)
  scope.stop()
})

it('renders clarification and errors without inventing a saved report', async () => {
  sessionStorage.setItem(`ka-project-assistant:${project.id}`, JSON.stringify({selectedId: task.id}))
  vi.mocked(api.getAssistantTask).mockResolvedValue({...task, result: {protocol: 'assistant-report-v1', action: 'ask_user', question: 'Which module?', report: null, references: []}})
  const wrapper = mount(ProjectAssistantPanel, {props: {projectId: project.id}}); await flushPromises()
  expect(wrapper.text()).toContain('Which module?')
  expect(wrapper.find('[aria-label="项目引用报告"]').exists()).toBe(false)
  vi.mocked(api.getAssistantTask).mockResolvedValue({...task, status: 'failed', error_code: 'AGENT_BUDGET_EXCEEDED', result: null})
  await wrapper.findAll('button').find(item => item.text() === '刷新助手任务')!.trigger('click'); await flushPromises()
  expect(wrapper.text()).toContain('AGENT_BUDGET_EXCEEDED')
  expect(api.startAssistantTask).not.toHaveBeenCalled()
})

it('clears source choices on project changes and provides source/context retry', async () => {
  vi.mocked(listSources).mockRejectedValueOnce(new Error('Source unavailable'))
  const wrapper = mount(ProjectAssistantPanel, {props: {projectId: project.id}}); await flushPromises()
  expect(wrapper.text()).toContain('Source unavailable')
  await wrapper.findAll('button').find(item => item.text() === '重新读取资料')!.trigger('click'); await flushPromises()
  vi.mocked(getCodeAnalysisContexts).mockRejectedValueOnce(new Error('Context unavailable'))
  await wrapper.get('.assistant-sources input[type=checkbox]').setValue(true); await flushPromises()
  expect(wrapper.text()).toContain('Context unavailable')
  await wrapper.findAll('button').find(item => item.text() === '重新读取快照')!.trigger('click'); await flushPromises()
  expect(wrapper.text()).not.toContain('Context unavailable')
  await wrapper.setProps({projectId: 'another-project'}); await flushPromises()
  expect(wrapper.text()).toContain('所选 0 份')
  expect(api.startAssistantTask).not.toHaveBeenCalled()
})

it('polls a queued task without submitting again and supports explicit cancel', async () => {
  const queued={...task,status:'queued' as const,execution_mode:'async_v2' as const,result:null,revision:0}
  vi.mocked(api.startAssistantTask).mockResolvedValue(queued)
  vi.mocked(api.getAssistantTask).mockResolvedValue(queued)
  vi.mocked(api.cancelAssistantTask).mockResolvedValue({...queued,status:'cancelled',revision:1})
  const wrapper=mount(ProjectAssistantPanel,{props:{projectId:project.id}});await flushPromises()
  await wrapper.get('textarea').setValue('Queue a goal');await wrapper.get('form').trigger('submit');await flushPromises()
  expect(wrapper.text()).toContain('等待独立 runner')
  expect(wrapper.get('fieldset').attributes('disabled')).toBeDefined()
  await wrapper.findAll('button').find(item=>item.text()==='取消后续步骤')!.trigger('click');await flushPromises()
  expect(api.cancelAssistantTask).toHaveBeenCalledWith(project.id,task.id)
  expect(api.startAssistantTask).toHaveBeenCalledOnce()
})

it('requires unknown-attempt acknowledgement and binds continuation to the saved revision/checkpoint', async () => {
  sessionStorage.setItem(`ka-project-assistant:${project.id}`,JSON.stringify({selectedId:task.id}))
  const interrupted={...task,status:'interrupted' as const,execution_mode:'async_v2' as const,can_continue:true,
    unknown_model_attempts:1,revision:3,checkpoint_id:'checkpoint-2',result:null}
  vi.mocked(api.getAssistantTask).mockResolvedValue(interrupted)
  vi.mocked(api.continueAssistantTask).mockResolvedValue({...interrupted,status:'queued',revision:4,can_continue:false})
  const wrapper=mount(ProjectAssistantPanel,{props:{projectId:project.id}});await flushPromises()
  const button=wrapper.findAll('button').find(item=>item.text()==='按保存检查点继续')!
  expect(button.attributes('disabled')).toBeDefined()
  const ack=wrapper.findAll('input[type=checkbox]').find(item=>item.element.parentElement?.textContent?.includes('结果未知'))!
  await ack.setValue(true)
  await button.trigger('click');await flushPromises()
  expect(api.continueAssistantTask).toHaveBeenCalledWith(project.id,task.id,expect.objectContaining({expected_revision:3,checkpoint_id:'checkpoint-2',acknowledge_unknown:true}))
  expect(api.startAssistantTask).not.toHaveBeenCalled()
})

it('retains the control UUID through an unknown response and reload for explicit idempotent retry',async()=>{
  sessionStorage.setItem(`ka-project-assistant:${project.id}`,JSON.stringify({selectedId:task.id}))
  const interrupted={...task,status:'interrupted' as const,execution_mode:'async_v2' as const,can_continue:true,unknown_model_attempts:0,revision:2,checkpoint_id:null}
  vi.mocked(api.getAssistantTask).mockResolvedValue(interrupted)
  vi.mocked(api.continueAssistantTask).mockRejectedValueOnce(new ApiError(0,{error:{message:'Control outcome unknown'}}))
  const wrapper=mount(ProjectAssistantPanel,{props:{projectId:project.id}});await flushPromises()
  await wrapper.findAll('button').find(item=>item.text()==='按保存检查点继续')!.trigger('click');await flushPromises()
  const input=vi.mocked(api.continueAssistantTask).mock.calls[0]![2]
  wrapper.unmount()
  vi.mocked(api.continueAssistantTask).mockResolvedValue({...interrupted,status:'queued',revision:3})
  const restored=mount(ProjectAssistantPanel,{props:{projectId:project.id}});await flushPromises()
  expect(api.continueAssistantTask).toHaveBeenCalledOnce()
  await restored.findAll('button').find(item=>item.text()==='按保存检查点继续')!.trigger('click');await flushPromises()
  expect(vi.mocked(api.continueAssistantTask).mock.calls[1]![2]).toEqual(input)
})

const proposed:api.AssistantOperation={id:'operation-1',kind:'propose_note_revision',status:'pending',proposal_sha256:'a'.repeat(64),payload:{arguments:{title:'<script>untrusted</script>',markdown:'New content'},before:{id:'original-revision'}},result:null,error_code:null}
const waiting:api.AssistantTask={...task,execution_mode:'async_v3',status:'waiting_approval',revision:2,result:null,operations:[proposed],can_continue:false}
it('shows full proposal inputs and binds human approval without auto-continuing',async()=>{
  sessionStorage.setItem(`ka-project-assistant:${project.id}`,JSON.stringify({selectedId:task.id}))
  const approved={...waiting,revision:3,operations:[{...proposed,status:'approved' as const}],can_continue:true}
  vi.mocked(api.getAssistantTask).mockResolvedValueOnce(waiting).mockResolvedValue(approved);vi.mocked(api.approveAssistantOperation).mockResolvedValue(approved)
  const wrapper=mount(ProjectAssistantPanel,{props:{projectId:project.id}});await flushPromises()
  expect(wrapper.text()).toContain('<script>untrusted</script>');expect(wrapper.find('script').exists()).toBe(false)
  await wrapper.findAll('button').find(b=>b.text()==='确认应用此提案')!.trigger('click');await flushPromises()
  expect(api.approveAssistantOperation).toHaveBeenCalledWith(project.id,task.id,expect.objectContaining({operation_id:proposed.id,proposal_sha256:proposed.proposal_sha256,decision:'approve'}))
  expect(api.continueAssistantTask).not.toHaveBeenCalled();expect(wrapper.text()).toContain('按保存检查点继续')
})
it('keeps an unknown approval UUID through reload for explicit same-decision replay',async()=>{
  sessionStorage.setItem(`ka-project-assistant:${project.id}`,JSON.stringify({selectedId:task.id}))
  vi.mocked(api.getAssistantTask).mockResolvedValue(waiting);vi.mocked(api.approveAssistantOperation).mockRejectedValueOnce(new ApiError(0,{error:{message:'Unknown approval'}}))
  const wrapper=mount(ProjectAssistantPanel,{props:{projectId:project.id}});await flushPromises()
  await wrapper.findAll('button').find(b=>b.text()==='拒绝此提案')!.trigger('click');await flushPromises()
  const original=vi.mocked(api.approveAssistantOperation).mock.calls[0]![2];wrapper.unmount()
  const restored=mount(ProjectAssistantPanel,{props:{projectId:project.id}});await flushPromises();expect(api.approveAssistantOperation).toHaveBeenCalledOnce()
  const rejected={...waiting,revision:3,operations:[{...proposed,status:'rejected' as const}],can_continue:true}
  vi.mocked(api.getAssistantTask).mockResolvedValue(rejected);vi.mocked(api.approveAssistantOperation).mockResolvedValue(rejected)
  await restored.findAll('button').find(b=>b.text()==='显式重发同一审批')!.trigger('click');await flushPromises()
  expect(vi.mocked(api.approveAssistantOperation).mock.calls[1]![2]).toEqual(original);expect(api.continueAssistantTask).not.toHaveBeenCalled()
})
it('opens an exact historical note revision from a report reference',async()=>{
  sessionStorage.setItem(`ka-project-assistant:${project.id}`,JSON.stringify({selectedId:task.id}))
  vi.mocked(api.getAssistantTask).mockResolvedValue({...task,result:{...task.result!,protocol:'assistant-report-v2',references:[{...task.result!.references[0]!,kind:'note',source_id:null,chunk_id:null,note_id:'note-id',revision_id:'revision-id'}]}})
  const wrapper=mount(ProjectAssistantPanel,{props:{projectId:project.id}});await flushPromises()
  await wrapper.findAll('button').find(b=>b.text()==='查看引用 1')!.trigger('click')
  expect(wrapper.emitted('openNote')).toEqual([['revision-id']]);expect(wrapper.emitted('openSource')).toBeUndefined()
})
