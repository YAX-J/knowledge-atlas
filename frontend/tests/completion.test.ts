import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { effectScope, reactive, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import * as api from '../src/api/workspace'
import { useConversations } from '../src/composables/useConversations'
import { useKnowledgeManagement } from '../src/composables/useKnowledgeManagement'
import KnowledgeManagement from '../src/components/KnowledgeManagement.vue'
import Workbench from '../src/components/Workbench.vue'
import AppHeader from '../src/components/AppHeader.vue'
import KnowledgeSearch from '../src/components/KnowledgeSearch.vue'
import type { Conversation, ConversationTurn, KnowledgeOperation, Page } from '../src/types'
import { project } from './fixtures'

vi.mock('../src/api/workspace')
const scopes: ReturnType<typeof effectScope>[] = []
const empty = <T>(): Page<T> => ({ items: [], total: 0, page: 1, page_size: 20 })
const conversation: Conversation = { id: 'conversation-1', project_id: project.id, title: 'Saved', created_at: project.created_at, updated_at: project.updated_at }
const turn: ConversationTurn = { id: 'turn-1', request_id: 'request-1', position: 1, question: 'Which database?', retrieval_mode: 'bm25', valid_at: null, status: 'succeeded', error_code: null, created_at: project.created_at,
  answer: { id: 'answer-1', question: 'Which database?', supported: false, answer: 'No evidence', confidence: 0, entity_ids: [], evidence: [], missing_information: ['Source'], retrieval: { keyword_hits: 0, vector_hits: 0, graph_hits: 0, indexed_count: 0, eligible_count: 0 } } }
function scope<T>(run: () => T) { const value = effectScope(); scopes.push(value); return value.run(run)! }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes }); return { promise, resolve } }
beforeEach(() => {
  sessionStorage.clear()
  vi.resetAllMocks()
  vi.mocked(api.listConversations).mockResolvedValue(empty())
  vi.mocked(api.listConversationTurns).mockResolvedValue(empty())
  vi.mocked(api.createConversation).mockResolvedValue(conversation)
  vi.mocked(api.askConversation).mockResolvedValue(turn)
  vi.mocked(api.listOperations).mockResolvedValue(empty())
  vi.mocked(api.getIdentity).mockResolvedValue({ entity_id: 'entity-1', canonical_id: 'entity-1', aliases: [], member_ids: ['entity-1'] })
})
afterEach(() => scopes.splice(0).forEach(value => value.stop()))

it('creates a persistent conversation once, rejects double send and reloads saved turns', async () => {
  const id = ref<string | undefined>(project.id)
  const state = scope(() => useConversations(() => id.value))
  await flushPromises()
  const pending = deferred<ConversationTurn>()
  vi.mocked(api.askConversation).mockReturnValueOnce(pending.promise)
  const request = state.send('Which database?', 'bm25')
  await flushPromises()
  await state.send('Double submit', 'bm25')
  expect(api.createConversation).toHaveBeenCalledOnce()
  expect(api.askConversation).toHaveBeenCalledOnce()
  vi.mocked(api.listConversationTurns).mockResolvedValue({ ...empty(), items: [turn], total: 1 })
  pending.resolve(turn); await request
  expect(state.result.value?.answer).toBe('No evidence')
  expect(state.turns.value?.items).toHaveLength(1)
  expect(state.sending.value).toBe(false)
})

it('fences late conversation results across a project round trip', async () => {
  const id = ref<string | undefined>(project.id)
  const state = scope(() => useConversations(() => id.value))
  await flushPromises()
  const pending = deferred<ConversationTurn>()
  vi.mocked(api.askConversation).mockReturnValueOnce(pending.promise)
  const request = state.send('Which database?', 'bm25')
  await flushPromises()
  id.value = 'other'; id.value = project.id
  pending.resolve(turn); await request; await flushPromises()
  expect(state.result.value).toBeNull()
  expect(state.selectedId.value).toBe('')
})

it('inspects an unknown result before allowing another paid request', async () => {
  const state = scope(() => useConversations(() => project.id))
  await flushPromises()
  vi.mocked(api.askConversation).mockRejectedValueOnce(new Error('Unknown result'))
  await state.send('Which database?', 'bm25')
  expect(state.unknown.value).toBe(true)
  await state.send('Which database?', 'bm25')
  expect(api.askConversation).toHaveBeenCalledOnce()
  const requestId = vi.mocked(api.askConversation).mock.calls[0]![2].request_id
  vi.mocked(api.listConversationTurns).mockResolvedValue({ ...empty(), items: [{ ...turn, request_id: requestId, status: 'interrupted', answer: null }], total: 1 })
  await state.refresh()
  expect(state.unknown.value).toBe(false)
  expect(state.retryTurn.value?.request_id).toBe(requestId)
  await state.send(turn.question, turn.retrieval_mode, state.retryTurn.value!)
  expect(vi.mocked(api.askConversation).mock.calls.at(-1)?.[2]).toMatchObject({ request_id: requestId, retry_interrupted: true })
})

it('retains an uncertain request id when the server history has not recorded it yet', async () => {
  const state = scope(() => useConversations(() => project.id))
  await flushPromises()
  vi.mocked(api.askConversation).mockRejectedValueOnce(new Error('Network result unknown'))
  await state.send('Delayed question', 'bm25')
  const requestId = vi.mocked(api.askConversation).mock.calls[0]![2].request_id
  await state.refresh()
  expect(state.unknown.value).toBe(false)
  expect(state.retryTurn.value?.request_id).toBe(requestId)
  const reopened = scope(() => useConversations(() => project.id))
  await flushPromises()
  await reopened.select(conversation.id)
  expect(reopened.retryTurn.value?.request_id).toBe(requestId)
  await state.send('Another question', 'bm25')
  expect(api.askConversation).toHaveBeenCalledOnce()
  await state.send('Delayed question', 'bm25', state.retryTurn.value!)
  expect(vi.mocked(api.askConversation).mock.calls[1]![2]).toMatchObject({ request_id: requestId, retry_interrupted: true })
})

it('reuses a knowledge operation request id on uncertain retry and blocks historical writes', async () => {
  const context = reactive({ projectId: project.id, entityId: 'entity-1', active: true, validAt: '' })
  const busy = ref(false), after = vi.fn(async () => {})
  const state = scope(() => useKnowledgeManagement(() => ({ ...context }), busy, after))
  await flushPromises()
  const input = { action: 'withdraw' as const, kind: 'entity' as const, knowledge_id: 'entity-1', reason: 'Reviewed evidence' }
  vi.mocked(api.operateKnowledge).mockRejectedValueOnce(new Error('Unknown'))
  await state.apply(input)
  const first = vi.mocked(api.operateKnowledge).mock.calls[0]![1].request_id
  vi.mocked(api.operateKnowledge).mockResolvedValue({ id: 'op', action: 'withdraw', reason: input.reason, payload: input, before: {}, after: {}, created_at: project.created_at })
  await state.apply(input)
  expect(vi.mocked(api.operateKnowledge).mock.calls[1]![1].request_id).toBe(first)
  expect(after).toHaveBeenCalledOnce()
  context.validAt = project.created_at
  await state.apply(input)
  expect(api.operateKnowledge).toHaveBeenCalledTimes(2)
})

it('requires a named operation preview and final confirmation', async () => {
  const wrapper = mount(KnowledgeManagement, { props: { nodes: [], selected: { id: 'entity-1', name: 'Storage choice', kind: 'entity' }, identity: null,
    operations: empty<KnowledgeOperation>(), retirements: [], changes: null, historical: false, busy: false, loading: false, error: '', notice: '' } })
  await wrapper.get('select').setValue('withdraw')
  await wrapper.get('textarea').setValue('The source contradicts it.')
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('apply')).toBeUndefined()
  expect(wrapper.get('[aria-label="知识操作最终确认"]').text()).toContain('Storage choice')
  await wrapper.findAll('button').find(item => item.text() === '确认执行')!.trigger('click')
  expect(wrapper.emitted('apply')?.[0]?.[0]).toMatchObject({ action: 'withdraw', knowledge_id: 'entity-1' })
  wrapper.unmount()
})

it('shows real workbench counts and emits real search from the header', async () => {
  const wrapper = mount(Workbench, { props: { project, projects: { items: [project], total: 1, page: 1, page_size: 20 },
    overview: { project_id: project.id, sources: 75, ready_sources: 72, pending_reviews: 4, entities: 12, relationships: 9, pending_tasks: 3 }, loading: false, error: '' } })
  expect(wrapper.text()).toContain('75 / 72')
  await wrapper.findAll('button').find(item => item.text() === '打开项目笔记')!.trigger('click')
  await wrapper.findAll('button').find(item => item.text() === '打开证据会话')!.trigger('click')
  expect(wrapper.emitted('navigate')).toEqual([['agents'], ['conversations']])
  const header = mount(AppHeader, { props: { nodes: [], selectedId: '', graphActive: false, projectName: project.name }, global: { stubs: { 'el-icon': true } } })
  await header.get('input').setValue('src/storage.py')
  await header.get('input').trigger('keydown.enter')
  expect(header.emitted('search')?.[0]).toEqual(['src/storage.py'])
  expect(header.emitted('select')).toBeUndefined()
  wrapper.unmount(); header.unmount()
})

it('reflects header search results without overwriting an unsent newer query', async () => {
  const wrapper = mount(KnowledgeSearch, { props: { result: null, loading: false, error: '', errorAction: 'search', labels: {}, rebuilding: false, notice: '' } })
  const result = { query: 'Storage', mode: 'bm25_source' as const, items: [], truncated: false, eligible_count: 0, indexed_count: null, weights: null }
  await wrapper.setProps({ result })
  expect((wrapper.get('input[type=search]').element as HTMLInputElement).value).toBe('Storage')
  expect((wrapper.get('#project-search-mode').element as HTMLSelectElement).value).toBe('bm25_source')
  await wrapper.get('input[type=search]').setValue('Unsent edit')
  await wrapper.setProps({ result: { ...result, query: 'Older response' } })
  expect((wrapper.get('input[type=search]').element as HTMLInputElement).value).toBe('Unsent edit')
  wrapper.unmount()
})
