import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import App from '../src/App.vue'
import SideRail from '../src/components/SideRail.vue'
import QuestionWorkspace from '../src/components/QuestionWorkspace.vue'
import SourceWorkspace from '../src/components/SourceWorkspace.vue'
import ProjectGraph from '../src/components/ProjectGraph.vue'
import * as api from '../src/api/knowledgeAtlas'
import { project } from './fixtures'
import type { EmbeddingIndexStatus, QuestionAnswer } from '../src/types'

vi.mock('../src/api/knowledgeAtlas', async importOriginal => {
  const original = await importOriginal<typeof api>()
  return { ...original, listProjects: vi.fn(), listSources: vi.fn(), listRepositories: vi.fn(), askQuestion: vi.fn(),
    getEmbeddingStatus: vi.fn(), getProjectGraph: vi.fn(), listKnowledgeChanges: vi.fn() }
})

it('keeps index status scoped to the selected project when an older inspection finishes late', async () => {
  vi.mocked(api.listProjects).mockResolvedValue({ items: [project], total: 1, page: 1, page_size: 20 })
  vi.mocked(api.listSources).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  vi.mocked(api.listRepositories).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  vi.mocked(api.getProjectGraph).mockResolvedValue({ nodes: [], edges: [], truncated: false })
  vi.mocked(api.listKnowledgeChanges).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  let resolveOld!: (value: EmbeddingIndexStatus) => void
  const current: EmbeddingIndexStatus = { model: 'current-model', dimensions: 1024, configured: false,
    checked_at: project.created_at, eligible_count: 0, indexed_count: 0, missing_count: 0, stale_count: 0,
    current_count: 0, scanned_count: 0, scan_limit: 1000, truncated: false }
  vi.mocked(api.getEmbeddingStatus).mockImplementationOnce(() => new Promise(yes => { resolveOld = yes }))
    .mockResolvedValueOnce(current)
  const wrapper = shallowMount(App)
  wrapper.getComponent(SideRail).vm.$emit('change', 'sources')
  await flushPromises()
  wrapper.getComponent(SourceWorkspace).vm.$emit('graph')
  await flushPromises()
  wrapper.getComponent(SideRail).vm.$emit('change', 'sources')
  await flushPromises()
  wrapper.getComponent(SourceWorkspace).vm.$emit('selectProject', { ...project, id: 'second-project' })
  await flushPromises()
  wrapper.getComponent(SourceWorkspace).vm.$emit('graph')
  await flushPromises()
  resolveOld({ ...current, model: 'old-project-model', eligible_count: 50 })
  await flushPromises()
  expect(api.getEmbeddingStatus).toHaveBeenLastCalledWith('second-project', '')
  expect(wrapper.getComponent(ProjectGraph).props('indexStatus')).toEqual(current)
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
