import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { effectScope, ref } from 'vue'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import * as api from '../src/api/agents'
import { ApiError } from '../src/api/client'
import { useAgentRuns } from '../src/composables/useAgentRuns'
import AgentWorkspace from '../src/pages/AgentWorkspace.vue'
import { project, source, answerFixture } from './fixtures'

vi.mock('../src/api/agents')
vi.mock('../src/components/agent/ProjectAssistantPanel.vue',()=>({default:{template:'<div />'}}))
enableAutoUnmount(afterEach)
const page=(items:api.AgentRun[]=[])=>({items,total:items.length,page:1,page_size:10})
const run:api.AgentRun={id:'run-1',project_id:project.id,source_id:source.id,kind:'knowledge_pipeline',
  status:'awaiting_review',result:{candidate_ids:['candidate'],extraction_task_id:'task'},
  events:[{sequence:1,agent:'knowledge_extraction',kind:'tool',tool_name:'read_chunk',status:'succeeded',elapsed_ms:2},
    {sequence:2,agent:'workflow',kind:'extraction_checkpoint',status:'saved',elapsed_ms:3}],
  usage:{model:2,tool:1,embedding:0},error_code:null,review_counts:{pending:1},created_at:project.created_at,updated_at:project.updated_at}
const props={project,projects:{items:[project],total:1,page:1,page_size:20},source}
beforeEach(()=>{
  vi.resetAllMocks();sessionStorage.clear()
  vi.mocked(api.listAgentRuns).mockResolvedValue(page())
  vi.mocked(api.getAgentRun).mockResolvedValue(run)
  vi.mocked(api.startAgentRun).mockResolvedValue(run)
  vi.mocked(api.resumeAgentRun).mockResolvedValue({...run,status:'succeeded',review_counts:{confirmed:1}})
})

it('reads saved claim mappings and forwards exact evidence without issuing another task',async()=>{
  const answer=answerFixture()
  vi.mocked(api.getAgentRun).mockResolvedValue({...run,kind:'question_pipeline',status:'succeeded',result:{answer}})
  const wrapper=mount(AgentWorkspace,{props:{...props,runId:run.id}});await flushPromises()
  expect(wrapper.get('[aria-label="协作回答"]').text()).toContain('Performance is unknown.')
  await wrapper.get('.claim-citations button').trigger('click')
  expect(wrapper.emitted('openEvidence')).toEqual([[answer.evidence[1]]])
  expect(api.startAgentRun).not.toHaveBeenCalled()
})

it('loads a lightweight history row and fetches its complete detail only when selected',async()=>{
  const {result:_result,events:_events,usage:_usage,review_counts:_counts,scope:_scope,...summary}=run
  vi.mocked(api.listAgentRuns).mockResolvedValue({items:[summary],total:1,page:1,page_size:10})
  const wrapper=mount(AgentWorkspace,{props});await flushPromises()
  expect(api.getAgentRun).not.toHaveBeenCalled()
  await wrapper.get('.agent-run-list button').trigger('click');await flushPromises()
  expect(api.getAgentRun).toHaveBeenCalledWith(project.id,run.id)
  expect(wrapper.text()).toContain('本次候选：待审核 1')
  expect(api.startAgentRun).not.toHaveBeenCalled()
})

it('starts an explicit workflow, opens its exact source and waits for human decisions before resume',async()=>{
  const wrapper=mount(AgentWorkspace,{props});await flushPromises()
  expect(wrapper.text()).toContain('还没有协作任务')
  await wrapper.get('form').trigger('submit');await flushPromises()
  expect(wrapper.text()).toContain('候选整理结果 · 已保存')
  expect(wrapper.text()).not.toContain('extraction_checkpoint')
  expect(api.startAgentRun).toHaveBeenCalledOnce()
  expect(vi.mocked(api.startAgentRun).mock.calls[0]![1]).toMatchObject({kind:'knowledge_pipeline',source_id:source.id,include_code_analysis:false,model_limit:8})
  const open=wrapper.findAll('button').find(item=>item.text()==='打开原文与候选审核')!
  await open.trigger('click');expect(wrapper.emitted('openSource')).toEqual([[source.id]])
  const resume=wrapper.findAll('button').find(item=>item.text()==='审核完成，继续流程')!
  expect(resume.attributes('disabled')).toBeDefined()
  vi.mocked(api.getAgentRun).mockResolvedValue({...run,review_counts:{confirmed:1}})
  await wrapper.findAll('button').find(item=>item.text()==='刷新任务与处理状态')!.trigger('click');await flushPromises()
  await resume.trigger('click');await flushPromises()
  expect(api.resumeAgentRun).toHaveBeenCalledWith(project.id,run.id)
  expect(wrapper.text()).toContain('已完成');expect(wrapper.emitted('run')?.[0]).toEqual([run.id])
})

it('preserves unknown submission UUID and only retries after an explicit user action',async()=>{
  vi.mocked(api.startAgentRun).mockRejectedValueOnce(new ApiError(0,{error:{code:'REQUEST_RESULT_UNKNOWN',message:'Unknown result'}}))
  const wrapper=mount(AgentWorkspace,{props});await flushPromises()
  await wrapper.get('form').trigger('submit');await flushPromises()
  const request=vi.mocked(api.startAgentRun).mock.calls[0]![1]
  expect(wrapper.text()).toContain('处理结果尚未确认');expect(api.startAgentRun).toHaveBeenCalledOnce()
  expect(wrapper.get('fieldset').attributes('disabled')).toBeDefined()
  vi.mocked(api.getAgentRun).mockRejectedValueOnce(new ApiError(404,{error:{code:'WORKFLOW_NOT_FOUND'}}))
  await wrapper.findAll('button').find(item=>item.text()==='刷新任务与处理状态')!.trigger('click');await flushPromises()
  expect(api.startAgentRun).toHaveBeenCalledOnce()
  await wrapper.findAll('button').find(item=>item.text()==='显式重发同一提交')!.trigger('click');await flushPromises()
  expect(api.startAgentRun).toHaveBeenCalledTimes(2)
  expect(vi.mocked(api.startAgentRun).mock.calls[1]![1]).toEqual(request)
})

it('restores a persisted pending request by reading status and never repeats its models',async()=>{
  sessionStorage.setItem('ka-pending-workflow:'+project.id,JSON.stringify({request_id:run.id,kind:'knowledge_pipeline',source_id:source.id}))
  const wrapper=mount(AgentWorkspace,{props});await flushPromises()
  expect(api.getAgentRun).toHaveBeenCalledWith(project.id,run.id)
  expect(wrapper.text()).toContain('等待人工审核')
  expect(api.startAgentRun).not.toHaveBeenCalled()
  expect(sessionStorage.getItem('ka-pending-workflow:'+project.id)).toBeNull()
})

it('does not publish a late workflow result after a project round trip or disposal',async()=>{
  const scope=effectScope(),currentProject=ref<string|undefined>(project.id)
  const state=scope.run(()=>useAgentRuns(()=>currentProject.value))!;await flushPromises()
  let finish!:(result:api.AgentRun)=>void
  vi.mocked(api.startAgentRun).mockReturnValueOnce(new Promise(yes=>{finish=yes}))
  const request=state.submit({kind:'knowledge_pipeline',source_id:source.id})
  vi.mocked(api.getAgentRun).mockRejectedValue(new ApiError(404,{error:{code:'WORKFLOW_NOT_FOUND'}}))
  currentProject.value='second-project';await flushPromises();currentProject.value=project.id;await flushPromises()
  scope.stop();finish(run);await request
  expect(state.selected.value).toBeNull()
})

it('blocks duplicate submits during execution and submits an explicit evidence question',async()=>{
  const wrapper=mount(AgentWorkspace,{props});await flushPromises()
  const selects=wrapper.findAll('select')
  await selects[1]!.setValue('question_pipeline')
  await wrapper.get('textarea').setValue('  Where is the evidence?  ')
  let finish!:(result:api.AgentRun)=>void
  vi.mocked(api.startAgentRun).mockReturnValueOnce(new Promise(yes=>{finish=yes}))
  await wrapper.get('form').trigger('submit');await flushPromises()
  await wrapper.get('form').trigger('submit')
  expect(api.startAgentRun).toHaveBeenCalledOnce()
  expect(vi.mocked(api.startAgentRun).mock.calls[0]![1]).toMatchObject({kind:'question_pipeline',question:'Where is the evidence?',retrieval_mode:'bm25'})
  finish({...run,kind:'question_pipeline',status:'succeeded'});await flushPromises()
})

it('opens a workflow deep link and blocks a new task while its server status is running',async()=>{
  vi.mocked(api.getAgentRun).mockResolvedValue({...run,status:'running'})
  const wrapper=mount(AgentWorkspace,{props:{...props,runId:run.id}});await flushPromises()
  expect(api.getAgentRun).toHaveBeenCalledWith(project.id,run.id)
  expect(wrapper.get('fieldset').attributes('disabled')).toBeDefined()
  await wrapper.get('form').trigger('submit');expect(api.startAgentRun).not.toHaveBeenCalled()
})

it('presents the actual pinned code context, uncovered calls and exact call quote',async()=>{
  vi.mocked(api.getAgentRun).mockResolvedValue({...run,status:'succeeded',result:{code_analysis:{
    source_id:source.id,language:'python',model:null,prompt_version:'test',strategy:'tools',
    context:{snapshot_id:'snapshot-1',commit_sha:'abc123',policy:'pinned'},
    calls:[{id:'call-1',caller_id:null,target_ids:[],receiver:'repo',callee_name:'save',line:12,column:1,
      call_quote:'repo.save()',resolution:'unresolved',confidence:0,resolution_basis:'Bounded candidates'}],
    related_symbols:[],scanned_source_count:2,detected_call_count:3,candidate_call_count:1,provider_call_count:2,
    uncovered_call_count:2,tool_call_count:1,tool_trace:[],truncated:true,has_syntax_errors:false,
  }}})
  const wrapper=mount(AgentWorkspace,{props:{...props,runId:run.id}});await flushPromises()
  const detail=wrapper.get('[aria-label="协作代码分析"]')
  expect(detail.text()).toContain('固定提交 abc123');expect(detail.text()).toContain('未覆盖 2 个')
  expect(detail.text()).toContain('结果不完整');expect(detail.get('pre').text()).toBe('repo.save()')
  expect(api.startAgentRun).not.toHaveBeenCalled()
})
