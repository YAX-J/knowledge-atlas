import { effectScope, reactive, ref } from 'vue'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import KnowledgeRetirement from '../src/components/KnowledgeRetirement.vue'
import { useKnowledgeRetirement } from '../src/composables/useKnowledgeRetirement'
import * as api from '../src/api/knowledgeAtlas'
import type { KnowledgeRetirement as Event, RetirementList } from '../src/types'
import { ApiError } from '../src/api/client'

vi.mock('../src/api/knowledgeAtlas',()=>({listKnowledgeRetirements:vi.fn(),retireKnowledge:vi.fn()}))
const scopes:ReturnType<typeof effectScope>[]=[]
enableAutoUnmount(afterEach)
afterEach(()=>scopes.splice(0).forEach(scope=>scope.stop()))
const empty:RetirementList={items:[],total:0,page:1,page_size:20}
const input={kind:'entity' as const,knowledge_id:'one',category:'correction' as const,reason:'人工核对发现错误。'}
const event:Event={...input,id:'event',project_id:'first',name:'Storage',effective_at:'2026-10-26T00:00:00Z',
  before:{valid_from:'2026-10-25T00:00:00Z',valid_to:null},after:{valid_from:'2026-10-25T00:00:00Z',valid_to:'2026-10-26T00:00:00Z'}}
beforeEach(()=>{vi.resetAllMocks();vi.mocked(api.listKnowledgeRetirements).mockResolvedValue(empty);vi.mocked(api.retireKnowledge).mockResolvedValue(event)})
function setup() {
  const context=reactive({projectId:'first',active:true,validAt:''}),busy=ref(false),done=vi.fn(async()=>{})
  const scope=effectScope();scopes.push(scope)
  return {context,busy,done,scope,state:scope.run(()=>useKnowledgeRetirement(()=>({...context}),busy,String,done))!}
}
it('requires a named target, reason and second confirmation; history and busy states remain read-only',async()=>{
  const wrapper=mount(KnowledgeRetirement,{props:{selected:{kind:'entity',id:'one',name:'<b>Storage</b>',current:true},records:empty,
    loading:false,error:'',actionError:'',notice:'',busy:false,historical:false}})
  expect(wrapper.find('b').exists()).toBe(false)
  await wrapper.get('textarea').setValue(input.reason)
  await wrapper.get('form').trigger('submit');expect(wrapper.emitted('retire')).toBeUndefined()
  expect(wrapper.text()).toContain('确认从现在起停用')
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('retire')?.[0]).toEqual([input])
  await wrapper.setProps({busy:true});await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('retire')).toHaveLength(1)
  await wrapper.setProps({busy:false,historical:true,records:{...empty,items:[event],total:1}})
  expect(wrapper.find('form').exists()).toBe(false)
  await wrapper.findAll('button').find(button=>button.text()==='查看停用前知识')!.trigger('click')
  expect(wrapper.emitted('visit')?.[0]).toEqual([event])
})
it('reuses the submission UUID after an unknown result and never automatically retries the write',async()=>{
  const {state,done}=setup()
  vi.mocked(api.retireKnowledge).mockRejectedValueOnce(new ApiError(0,{error:{code:'REQUEST_RESULT_UNKNOWN',message:'结果未知'}}))
  await state.retireKnowledge(input)
  const first=vi.mocked(api.retireKnowledge).mock.calls[0]![1]
  expect(state.retirementError.value).toContain('结果未知')
  await state.loadRetirements();expect(api.retireKnowledge).toHaveBeenCalledOnce()
  await state.retireKnowledge(input)
  expect(api.retireKnowledge).toHaveBeenLastCalledWith('first',first)
  expect(done).toHaveBeenCalledOnce()
  expect(state.retirementNotice.value).toContain('历史与原文仍保留')
})
it('fences audit reads across project round trips and blocks history writes',async()=>{
  const {state,context}=setup()
  let resolve!: (value:RetirementList)=>void
  vi.mocked(api.listKnowledgeRetirements).mockReturnValueOnce(new Promise(yes=>{resolve=yes}))
  const pending=state.loadRetirements()
  context.projectId='second';context.projectId='first'
  await flushPromises()
  resolve({...empty,items:[event],total:1});await pending
  expect(state.retirements.value?.total).toBe(0)
  context.validAt='2026-10-25T00:00:00Z';await state.retireKnowledge(input)
  expect(api.retireKnowledge).not.toHaveBeenCalled()
})
it('holds the shared mutation lock and discards a late successful write after unmount',async()=>{
  const {state,scope,busy,done}=setup()
  let resolve!: (value:Event)=>void
  vi.mocked(api.retireKnowledge).mockReturnValueOnce(new Promise(yes=>{resolve=yes}))
  const pending=state.retireKnowledge(input)
  expect(busy.value).toBe(true)
  await state.retireKnowledge(input);expect(api.retireKnowledge).toHaveBeenCalledOnce()
  scope.stop();resolve(event);await pending
  expect(done).not.toHaveBeenCalled();expect(busy.value).toBe(false)
})
