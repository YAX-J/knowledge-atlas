import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import * as api from '../src/api/workspace'
import ConversationsWorkspace from '../src/components/ConversationsWorkspace.vue'
import KnowledgeManagement from '../src/components/KnowledgeManagement.vue'
import type { Conversation, ConversationTurn, FormalKnowledgeNode, KnowledgeOperation, Page, QuestionAnswer } from '../src/types'
import { project } from './fixtures'

vi.mock('../src/api/workspace')
enableAutoUnmount(afterEach)
const page = <T>(items:T[] = []):Page<T> => ({items,total:items.length,page:1,page_size:20})
const conversation:Conversation={id:'conversation',project_id:project.id,title:'Saved evidence',created_at:project.created_at,updated_at:project.updated_at}
const answer:QuestionAnswer={id:'answer',question:'Where?',supported:false,answer:'Need more source evidence',confidence:0,entity_ids:[],evidence:[],
  missing_information:['Source'],retrieval:{keyword_hits:0,vector_hits:0,graph_hits:0,indexed_count:0,eligible_count:0}}
const turn:ConversationTurn={id:'turn',request_id:'request',question:'Where?',position:1,retrieval_mode:'bm25',valid_at:null,status:'succeeded',answer,error_code:null,created_at:project.created_at}
const props={project,projects:{items:[project],total:1,page:1,page_size:20},projectsLoading:false,projectsError:''}
const node=(id:string,type:string,name:string):FormalKnowledgeNode=>({id,type,name,project_id:project.id,candidate_id:id,
  summary:name,confidence:.9,status:'active',valid_from:project.created_at,valid_to:null,evidence_count:1})
beforeEach(()=>{
  vi.resetAllMocks();sessionStorage.clear()
  vi.mocked(api.listConversations).mockResolvedValue(page())
  vi.mocked(api.listConversationTurns).mockResolvedValue(page())
  vi.mocked(api.createConversation).mockResolvedValue(conversation)
  vi.mocked(api.askConversation).mockResolvedValue(turn)
})

it('recovers from a list error then requires inspection and explicit consent before retrying an uncertain turn',async()=>{
  vi.mocked(api.listConversations).mockRejectedValueOnce(new Error('List unavailable'))
  const wrapper=mount(ConversationsWorkspace,{props})
  await flushPromises()
  expect(wrapper.text()).toContain('List unavailable')
  await wrapper.findAll('button').find(item=>item.text()==='刷新会话与处理状态')!.trigger('click');await flushPromises()
  expect(wrapper.text()).toContain('还没有会话')
  vi.mocked(api.askConversation).mockRejectedValueOnce(new Error('Timed out; result unknown'))
  await wrapper.get('textarea').setValue('Where?')
  await wrapper.get('.ask-card form').trigger('submit');await flushPromises()
  const requestId=vi.mocked(api.askConversation).mock.calls[0]![2].request_id
  expect(wrapper.text()).toContain('请先刷新状态')
  expect(api.askConversation).toHaveBeenCalledOnce()
  vi.mocked(api.listConversationTurns).mockResolvedValue(page([{...turn,request_id:requestId,status:'interrupted',answer:null}]))
  await wrapper.findAll('button').find(item=>item.text()==='刷新会话与处理状态')!.trigger('click');await flushPromises()
  const retry=wrapper.findAll('button').find(item=>item.text()==='重新请求')!
  expect(retry.attributes('disabled')).toBeDefined()
  await wrapper.get('.conversation-history input[type=checkbox]').setValue(true)
  vi.mocked(api.listConversationTurns).mockResolvedValue(page([{...turn,request_id:requestId}]))
  await wrapper.get('.conversation-history form').trigger('submit');await flushPromises()
  expect(api.askConversation).toHaveBeenCalledTimes(2)
  expect(vi.mocked(api.askConversation).mock.calls[1]![2]).toMatchObject({request_id:requestId,retry_interrupted:true})
  expect(wrapper.text()).toContain(answer.answer)
})

it('opens saved history, paginates turns and discards a late read after a project switch',async()=>{
  vi.mocked(api.listConversations).mockResolvedValue(page([conversation]))
  vi.mocked(api.listConversationTurns).mockResolvedValue({...page([turn]),total:21})
  const wrapper=mount(ConversationsWorkspace,{props});await flushPromises()
  await wrapper.get('.conversation-list button').trigger('click');await flushPromises()
  expect(wrapper.text()).toContain('历史回答保存当时的证据快照')
  await wrapper.get('[aria-label="问答轮次分页"]').findAll('button')[1]!.trigger('click');await flushPromises()
  expect(api.listConversationTurns).toHaveBeenLastCalledWith(project.id,conversation.id,2)
  let finish!:(value:Page<ConversationTurn>)=>void
  vi.mocked(api.listConversationTurns).mockReturnValueOnce(new Promise(resolve=>{finish=resolve}))
  await wrapper.findAll('button').find(item=>item.text()==='刷新会话与处理状态')!.trigger('click');await flushPromises()
  vi.mocked(api.listConversations).mockResolvedValue(page())
  await wrapper.setProps({project:{...project,id:'other-project'}});await flushPromises()
  finish(page([{...turn,answer:{...answer,answer:'Late private context'}}]));await flushPromises()
  expect(wrapper.text()).not.toContain('Late private context')
  expect(wrapper.text()).not.toContain('Saved evidence')
})

it('creates an explicit conversation and does not send a duplicate while the first request is pending',async()=>{
  const wrapper=mount(ConversationsWorkspace,{props});await flushPromises()
  await wrapper.findAll('button').find(item=>item.text()==='新建会话')!.trigger('click');await flushPromises()
  expect(api.createConversation).toHaveBeenCalledOnce()
  let finish!:(value:ConversationTurn)=>void
  vi.mocked(api.askConversation).mockReturnValueOnce(new Promise(resolve=>{finish=resolve}))
  await wrapper.get('textarea').setValue('Where?')
  await wrapper.get('.ask-card form').trigger('submit');await flushPromises()
  expect(wrapper.get('textarea').attributes('disabled')).toBeDefined()
  await wrapper.get('.ask-card form').trigger('submit')
  expect(api.askConversation).toHaveBeenCalledOnce()
  finish(turn);await flushPromises()
})

it('blocks historical identity writes and previews both names before a current merge',async()=>{
  const wrapper=mount(KnowledgeManagement,{props:{nodes:[
    node('old','Concept','Old identity'),node('keep','Concept','Canonical identity'),node('wrong','Technology','Wrong type')],
    selected:{id:'old',name:'Old identity',kind:'entity'},identity:null,operations:page<KnowledgeOperation>(),retirements:[],changes:null,
    historical:true,busy:false,loading:false,error:'',notice:''}})
  expect(wrapper.get('fieldset').attributes('disabled')).toBeDefined()
  await wrapper.get('form').trigger('submit');expect(wrapper.emitted('apply')).toBeUndefined()
  await wrapper.setProps({historical:false})
  await wrapper.get('select').setValue('merge')
  expect(wrapper.text()).not.toContain('Wrong type')
  await wrapper.findAll('select')[1]!.setValue('keep')
  await wrapper.get('textarea').setValue('Both cite the same source concept')
  await wrapper.get('form').trigger('submit')
  const preview=wrapper.get('[aria-label="知识操作最终确认"]')
  expect(preview.text()).toContain('Old identity');expect(preview.text()).toContain('Canonical identity')
  expect(wrapper.emitted('apply')).toBeUndefined()
  await preview.findAll('button')[0]!.trigger('click')
  expect(wrapper.emitted('apply')?.[0]?.[0]).toMatchObject({action:'merge',knowledge_id:'old',target_id:'keep'})
})
