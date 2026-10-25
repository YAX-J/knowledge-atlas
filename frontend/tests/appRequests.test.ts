import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import App from '../src/App.vue'
import SideRail from '../src/components/SideRail.vue'
import QuestionWorkspace from '../src/components/QuestionWorkspace.vue'
import * as api from '../src/api/knowledgeAtlas'
import { project } from './fixtures'
import type { QuestionAnswer } from '../src/types'

vi.mock('../src/api/knowledgeAtlas', async importOriginal => {
  const original = await importOriginal<typeof api>()
  return { ...original, listProjects: vi.fn(), listSources: vi.fn(), listRepositories: vi.fn(), askQuestion: vi.fn() }
})
enableAutoUnmount(afterEach)

it('App preserves request mode on retry and drops late answers after clear or project switch', async () => {
  vi.mocked(api.listProjects).mockResolvedValue({ items: [project], total: 1, page: 1, page_size: 20 })
  vi.mocked(api.listSources).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  vi.mocked(api.listRepositories).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  const wrapper = shallowMount(App)
  wrapper.getComponent(SideRail).vm.$emit('change', 'questions')
  await flushPromises()
  let resolve!: (value: QuestionAnswer) => void
  vi.mocked(api.askQuestion).mockImplementation(() => new Promise(yes => { resolve = yes }))
  const answer: QuestionAnswer = { id: 'answer', question: 'Question', answer: 'Old answer', supported: false,
    confidence: 0, evidence: [], entity_ids: [], missing_information: ['Missing'],
    retrieval: { keyword_hits: 0, vector_hits: 0, graph_hits: 0, eligible_count: 0, indexed_count: 0 } }
  wrapper.getComponent(QuestionWorkspace).vm.$emit('ask', 'Question', 'rrf')
  await flushPromises()
  expect(api.askQuestion).toHaveBeenLastCalledWith(project.id, 'Question', 'rrf')
  wrapper.getComponent(QuestionWorkspace).vm.$emit('clear')
  resolve(answer)
  await flushPromises()
  expect(wrapper.getComponent(QuestionWorkspace).props('result')).toBeNull()
  wrapper.getComponent(QuestionWorkspace).vm.$emit('ask', 'Question', 'bm25')
  await flushPromises()
  wrapper.getComponent(QuestionWorkspace).vm.$emit('selectProject', { ...project, id: 'second-project' })
  resolve(answer)
  await flushPromises()
  expect(wrapper.getComponent(QuestionWorkspace).props('result')).toBeNull()
  vi.mocked(api.askQuestion).mockRejectedValueOnce(new Error('Transient failure'))
  wrapper.getComponent(QuestionWorkspace).vm.$emit('ask', 'Retry question', 'vector')
  await flushPromises()
  expect(wrapper.getComponent(QuestionWorkspace).props('error')).toBeTruthy()
  vi.mocked(api.askQuestion).mockResolvedValueOnce(answer)
  wrapper.getComponent(QuestionWorkspace).vm.$emit('retry')
  await flushPromises()
  expect(api.askQuestion).toHaveBeenLastCalledWith('second-project', 'Retry question', 'vector')
  expect(wrapper.getComponent(QuestionWorkspace).props('result')).toEqual(answer)
})
