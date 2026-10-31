import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { effectScope, ref } from 'vue'
import * as api from '../src/api/agents'
import { getCodeAnalysisContexts, type CodeAnalysisContexts } from '../src/api/knowledgeAtlas'
import { useCodeContextSelection } from '../src/composables/useCodeContextSelection'
import AgentWorkspace from '../src/pages/AgentWorkspace.vue'
vi.mock('../src/components/agent/ProjectAssistantPanel.vue',()=>({default:{template:'<div />'}}))
import { project, source } from './fixtures'

vi.mock('../src/api/agents')
vi.mock('../src/api/knowledgeAtlas', () => ({ getCodeAnalysisContexts: vi.fn() }))
enableAutoUnmount(afterEach)
const local:CodeAnalysisContexts={default_snapshot_id:null,snapshots:[],truncated:false,
  version_groups:[{path:'helper.ts',truncated:true,versions:[
    {id:'new-helper',created_at:project.created_at,size_bytes:100},
    {id:'old-helper',created_at:'2026-10-01T00:00:00Z',size_bytes:90}]}]}
const snapshots:CodeAnalysisContexts={...local,default_snapshot_id:'new-commit',snapshots:[
  {id:'new-commit',ref:'main',commit_sha:'b'.repeat(40),truncated:false},
  {id:'old-commit',ref:'release',commit_sha:'a'.repeat(40),truncated:true}]}
const record:api.AgentRun={id:'run-1',project_id:project.id,source_id:source.id,kind:'knowledge_pipeline',
  status:'succeeded',result:null,events:[],usage:{},error_code:null,review_counts:{},
  created_at:project.created_at,updated_at:project.updated_at}
const props={project,projects:{items:[project],total:1,page:1,page_size:20},source:{...source,source_type:'typescript'}}
beforeEach(()=>{
  vi.resetAllMocks();sessionStorage.clear()
  vi.mocked(api.listAgentRuns).mockResolvedValue({items:[],total:0,page:1,page_size:10})
  vi.mocked(api.startAgentRun).mockResolvedValue(record)
  vi.mocked(api.getAgentRun).mockResolvedValue(record)
  vi.mocked(getCodeAnalysisContexts).mockResolvedValue(local)
})

it('selects a pinned commit and sends it without local version overrides',async()=>{
  vi.mocked(getCodeAnalysisContexts).mockResolvedValue(snapshots)
  const wrapper=mount(AgentWorkspace,{props});await flushPromises()
  await wrapper.get('input[type=checkbox]').setValue(true);await flushPromises()
  expect(getCodeAnalysisContexts).toHaveBeenCalledWith(source.id)
  expect(api.startAgentRun).not.toHaveBeenCalled()
  await wrapper.get('[aria-label="协作提交快照"]').setValue('old-commit')
  await wrapper.get('[aria-label="协作代码分析方式"]').setValue('semantic')
  expect(wrapper.get('[aria-label="本次任务范围"]').text()).toContain('固定提交 aaaaaaaaaaaa')
  expect(wrapper.find('[aria-label="协作相关文件版本 helper.ts"]').exists()).toBe(false)
  await wrapper.get('form').trigger('submit');await flushPromises()
  const input=vi.mocked(api.startAgentRun).mock.calls[0]![1]
  expect(input).toMatchObject({snapshot_id:'old-commit',include_code_analysis:true,code_strategy:'semantic'})
  expect(input.version_ids).toBeUndefined()
})

it('shows bounded local version choices and submits only explicit overrides',async()=>{
  const wrapper=mount(AgentWorkspace,{props});await flushPromises()
  await wrapper.get('input[type=checkbox]').setValue(true);await flushPromises()
  expect(wrapper.text()).toContain('未指定的相关文件取执行时最新已解析版本')
  expect(wrapper.text()).toContain('仅列出部分版本')
  await wrapper.get('[aria-label="协作相关文件版本 helper.ts"]').setValue('old-helper')
  await wrapper.get('form').trigger('submit');await flushPromises()
  const input=vi.mocked(api.startAgentRun).mock.calls[0]![1]
  expect(input.version_ids).toEqual(['old-helper'])
  expect(input.snapshot_id).toBeUndefined()
})

it('chooses retrieval and historical time while discarding current-code selections',async()=>{
  vi.mocked(getCodeAnalysisContexts).mockResolvedValue(snapshots)
  const wrapper=mount(AgentWorkspace,{props});await flushPromises()
  await wrapper.findAll('select')[1]!.setValue('question_pipeline')
  await wrapper.get('textarea').setValue('Historical decision')
  await wrapper.get('input[type=checkbox]').setValue(true);await flushPromises()
  await wrapper.get('[aria-label="协作提交快照"]').setValue('old-commit')
  await wrapper.get('[aria-label="协作检索方式"]').setValue('bm25_source')
  await wrapper.get('[aria-label="协作知识时间"]').setValue('2026-10-01T10:30')
  expect(wrapper.get('input[type=checkbox]').attributes('disabled')).toBeDefined()
  expect(wrapper.find('[aria-label="代码版本选择"]').exists()).toBe(false)
  expect(wrapper.text()).toContain('历史问答仅检索当时有效的正式证据')
  await wrapper.get('form').trigger('submit');await flushPromises()
  const input=vi.mocked(api.startAgentRun).mock.calls[0]![1]
  expect(input).toMatchObject({retrieval_mode:'bm25_source',valid_at:new Date('2026-10-01T10:30').toISOString(),include_code_analysis:false})
  expect(input.snapshot_id).toBeUndefined();expect(input.version_ids).toBeUndefined();expect(input.source_id).toBeUndefined()
})

it('submits a selected fusion mode without silently replacing it with the default',async()=>{
  const wrapper=mount(AgentWorkspace,{props});await flushPromises()
  await wrapper.findAll('select')[1]!.setValue('question_pipeline')
  await wrapper.get('textarea').setValue('Recall this decision')
  await wrapper.get('[aria-label="协作检索方式"]').setValue('rrf')
  expect(wrapper.get('[aria-label="本次任务范围"]').text()).toContain('BM25 + 向量融合')
  await wrapper.get('form').trigger('submit');await flushPromises()
  expect(vi.mocked(api.startAgentRun).mock.calls[0]![1]).toMatchObject({retrieval_mode:'rrf'})
})

it('blocks paid submission when context reads fail and retries only the read',async()=>{
  vi.mocked(getCodeAnalysisContexts).mockRejectedValueOnce(new Error('读取版本暂不可用'))
  const wrapper=mount(AgentWorkspace,{props});await flushPromises()
  await wrapper.get('input[type=checkbox]').setValue(true);await flushPromises()
  expect(wrapper.get('[type=submit]').attributes('disabled')).toBeDefined()
  await wrapper.get('form').trigger('submit');expect(api.startAgentRun).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('读取版本暂不可用')
  await wrapper.findAll('button').find(item=>item.text()==='重试读取代码版本')!.trigger('click');await flushPromises()
  expect(getCodeAnalysisContexts).toHaveBeenCalledTimes(2)
  expect(wrapper.get('[type=submit]').attributes('disabled')).toBeUndefined()
  expect(api.startAgentRun).not.toHaveBeenCalled()
})

it('resets source selections and compiler strategy when the source changes',async()=>{
  const wrapper=mount(AgentWorkspace,{props});await flushPromises()
  await wrapper.get('input[type=checkbox]').setValue(true);await flushPromises()
  await wrapper.get('[aria-label="协作代码分析方式"]').setValue('semantic')
  await wrapper.get('[aria-label="协作相关文件版本 helper.ts"]').setValue('old-helper')
  await wrapper.setProps({source:{...source,id:'second-source'}})
  expect((wrapper.get('input[type=checkbox]').element as HTMLInputElement).checked).toBe(false)
  await wrapper.get('input[type=checkbox]').setValue(true);await flushPromises()
  expect(wrapper.get('[aria-label="协作代码分析方式"]').element).toHaveProperty('value','single_step')
  expect(wrapper.get('[aria-label="协作相关文件版本 helper.ts"]').element).toHaveProperty('value','')
})

it('restores saved scope by GET and keeps it distinct from the new draft',async()=>{
  const saved={...record,kind:'question_pipeline',scope:{retrieval_mode:'rrf' as const,valid_at:'2026-10-01T02:30:00Z',
    include_code_analysis:false,code_strategy:null,snapshot_id:null,version_ids:[]}}
  vi.mocked(api.getAgentRun).mockResolvedValue(saved)
  const wrapper=mount(AgentWorkspace,{props:{...props,runId:record.id}});await flushPromises()
  expect(wrapper.get('[aria-label="所选任务范围"]').text()).toContain('BM25 + 向量融合')
  expect(wrapper.get('[aria-label="所选任务范围"]').text()).not.toContain('当前有效知识')
  expect(api.startAgentRun).not.toHaveBeenCalled()
})

it('discards late context results across a source round trip and disposal',async()=>{
  const current=ref('source-a'),enabled=ref(true)
  const finishes:Array<(value:CodeAnalysisContexts)=>void>=[]
  vi.mocked(getCodeAnalysisContexts).mockImplementation(()=>new Promise(resolve=>finishes.push(resolve)))
  const scope=effectScope()
  const state=scope.run(()=>useCodeContextSelection(()=>project.id,()=>current.value,()=>enabled.value))!
  current.value='source-b';current.value='source-a'
  finishes[0]!(snapshots);await flushPromises();expect(state.contexts.value).toBeNull()
  finishes[2]!(local);await flushPromises();expect(state.contexts.value).toEqual(local)
  expect(state.snapshotId.value).toBe('')
  scope.stop();finishes[1]!(snapshots);await flushPromises()
  expect(state.contexts.value).toBeNull()
})

it('validates local overrides before they can enter a workflow request',async()=>{
  const scope=effectScope()
  const groups=Array.from({length:100},(_,index)=>({path:`file-${index}.ts`,truncated:false,
    versions:[{id:`version-${index}`,created_at:project.created_at,size_bytes:1}]}))
  vi.mocked(getCodeAnalysisContexts).mockResolvedValue({...local,version_groups:groups})
  const state=scope.run(()=>useCodeContextSelection(()=>project.id,()=>source.id,()=>true))!
  await flushPromises()
  state.versions.value={unknown:'foreign-version'}
  expect(state.ready.value).toBe(false)
  state.versions.value=Object.fromEntries(groups.map(group=>[group.path,group.versions[0]!.id]))
  expect(state.validationError.value).toContain('99')
  expect(state.ready.value).toBe(false)
  scope.stop()
})

it('never reads or submits a source outside the selected project',async()=>{
  const wrapper=mount(AgentWorkspace,{props:{...props,source:{...props.source,project_id:'another-project'}}})
  await flushPromises()
  expect(wrapper.find('input[type=checkbox]').exists()).toBe(false)
  expect(wrapper.get('[type=submit]').attributes('disabled')).toBeDefined()
  await wrapper.get('form').trigger('submit')
  expect(getCodeAnalysisContexts).not.toHaveBeenCalled()
  expect(api.startAgentRun).not.toHaveBeenCalled()
  await wrapper.findAll('select')[1]!.setValue('question_pipeline')
  await wrapper.get('textarea').setValue('Question for this project')
  await wrapper.get('form').trigger('submit');await flushPromises()
  const [selectedProject,input]=vi.mocked(api.startAgentRun).mock.calls[0]!
  expect(selectedProject).toBe(project.id)
  expect(input.source_id).toBeUndefined();expect(input.include_code_analysis).toBe(false)
})

it('omits empty scope regions for source-only knowledge preparation',async()=>{
  vi.mocked(api.getAgentRun).mockResolvedValue({...record,scope:{retrieval_mode:null,valid_at:null,
    include_code_analysis:false,code_strategy:null,snapshot_id:null,version_ids:[]}})
  const wrapper=mount(AgentWorkspace,{props:{...props,runId:record.id}});await flushPromises()
  expect(wrapper.find('[aria-label="本次任务范围"]').exists()).toBe(false)
  expect(wrapper.find('[aria-label="所选任务范围"]').exists()).toBe(false)
  expect(wrapper.text()).toContain('当前资料')
})
