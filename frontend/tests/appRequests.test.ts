import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, shallowMount } from '@vue/test-utils'
import App from '../src/App.vue'
import SideRail from '../src/components/SideRail.vue'
import QuestionWorkspace from '../src/components/QuestionWorkspace.vue'
import SourceWorkspace from '../src/components/SourceWorkspace.vue'
import ProjectGraph from '../src/components/ProjectGraph.vue'
import CandidateReview from '../src/components/CandidateReview.vue'
import KnowledgeEvolution from '../src/components/KnowledgeEvolution.vue'
import * as api from '../src/api/knowledgeAtlas'
import { project, source } from './fixtures'
import type { EmbeddingIndexStatus, EmbeddingRebuildResult, EntityDetail, KnowledgeSearchResult, QuestionAnswer } from '../src/types'

vi.mock('../src/api/knowledgeAtlas', async importOriginal => {
  const original = await importOriginal<typeof api>()
  return { ...original, listProjects: vi.fn(), listSources: vi.fn(), listRepositories: vi.fn(), askQuestion: vi.fn(),
    getEmbeddingStatus: vi.fn(), getProjectGraph: vi.fn(), listKnowledgeChanges: vi.fn(), getEntityDetail: vi.fn(),
    getSource: vi.fn(), listSourceChunks: vi.fn(), listCandidates: vi.fn(), getExtraction: vi.fn(),
    searchKnowledge: vi.fn(), rebuildProjectEmbeddings: vi.fn() }
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
beforeEach(() => vi.resetAllMocks())

async function openSearchGraph() {
  vi.mocked(api.listProjects).mockResolvedValue({ items: [project], total: 1, page: 1, page_size: 20 })
  vi.mocked(api.listSources).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  vi.mocked(api.listRepositories).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  vi.mocked(api.getProjectGraph).mockResolvedValue({ nodes: [], edges: [], truncated: false })
  vi.mocked(api.listKnowledgeChanges).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  const wrapper = shallowMount(App)
  wrapper.getComponent(SideRail).vm.$emit('change', 'sources')
  await flushPromises()
  wrapper.getComponent(SourceWorkspace).vm.$emit('graph')
  await flushPromises()
  return wrapper
}

const searchResult: KnowledgeSearchResult = { query: 'Storage', mode: 'bm25', items: [], truncated: false,
  indexed_count: null, eligible_count: 0, weights: null }

it('wires search retry and drops a late result after clear in the graph page', async () => {
  const wrapper = await openSearchGraph()
  vi.mocked(api.searchKnowledge).mockRejectedValueOnce(new Error('Unavailable')).mockResolvedValueOnce(searchResult)
  wrapper.getComponent(ProjectGraph).vm.$emit('search', 'Storage', 'Technology', 'bm25')
  await flushPromises()
  expect(wrapper.getComponent(ProjectGraph).props('searchError')).toBeTruthy()
  wrapper.getComponent(ProjectGraph).vm.$emit('retrySearch')
  await flushPromises()
  expect(api.searchKnowledge).toHaveBeenLastCalledWith(project.id, 'Storage', 'Technology', 'bm25', '')
  expect(wrapper.getComponent(ProjectGraph).props('searchResult')).toEqual(searchResult)
  let finish!: (value: KnowledgeSearchResult) => void
  vi.mocked(api.searchKnowledge).mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  wrapper.getComponent(ProjectGraph).vm.$emit('search', 'Late search', '', 'vector')
  await flushPromises()
  wrapper.getComponent(ProjectGraph).vm.$emit('clearSearch')
  finish(searchResult)
  await flushPromises()
  expect(wrapper.getComponent(ProjectGraph).props('searchResult')).toBeNull()
  expect(wrapper.getComponent(ProjectGraph).props('searchLoading')).toBe(false)
})

it('keeps the graph rebuild control busy after clear until the actual request finishes', async () => {
  const wrapper = await openSearchGraph()
  let finish!: (value: EmbeddingRebuildResult) => void
  vi.mocked(api.rebuildProjectEmbeddings).mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  wrapper.getComponent(ProjectGraph).vm.$emit('rebuildSearch')
  await flushPromises()
  wrapper.getComponent(ProjectGraph).vm.$emit('clearSearch')
  wrapper.getComponent(ProjectGraph).vm.$emit('rebuildSearch')
  await flushPromises()
  expect(api.rebuildProjectEmbeddings).toHaveBeenCalledTimes(1)
  expect(wrapper.getComponent(ProjectGraph).props('searchRebuilding')).toBe(true)
  finish({ model: 'test', dimensions: 1024, eligible_count: 1, updated_count: 1, reused_count: 0 })
  await flushPromises()
  expect(wrapper.getComponent(ProjectGraph).props('searchRebuilding')).toBe(false)
  expect(wrapper.getComponent(ProjectGraph).props('searchNotice')).toBe('')
})

it('drops a graph search after switching the effective time', async () => {
  const wrapper = await openSearchGraph()
  let finish!: (value: KnowledgeSearchResult) => void
  vi.mocked(api.searchKnowledge).mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  wrapper.getComponent(ProjectGraph).vm.$emit('search', 'Storage', '', 'rrf')
  await flushPromises()
  wrapper.getComponent(ProjectGraph).vm.$emit('time', '2026-10-24T00:00:00Z')
  await flushPromises()
  finish(searchResult)
  await flushPromises()
  expect(wrapper.getComponent(ProjectGraph).props('searchResult')).toBeNull()
  expect(wrapper.getComponent(ProjectGraph).props('searchLoading')).toBe(false)
})

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

it('does not restore closed comparisons or display entities from a different project', async () => {
  vi.mocked(api.listProjects).mockResolvedValue({ items: [project], total: 1, page: 1, page_size: 20 })
  vi.mocked(api.listSources).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  vi.mocked(api.listRepositories).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  vi.mocked(api.getProjectGraph).mockResolvedValue({ nodes: [], edges: [], truncated: false })
  vi.mocked(api.listKnowledgeChanges).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  const detail = (id: string): EntityDetail => ({ entity: { id, project_id: project.id, candidate_id: id,
    type: 'Decision', name: id, summary: id, confidence: .8, status: 'active', valid_from: project.created_at,
    valid_to: null, evidence_count: 0 }, evidence: [], relationships: [], truncated: false })
  let finish!: (value: EntityDetail) => void
  vi.mocked(api.getEntityDetail).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    .mockResolvedValueOnce(detail('second'))
  const wrapper = shallowMount(App, { global: { stubs: { ProjectGraph: { template: '<div><slot name="evolution" /></div>' } } } })
  wrapper.getComponent(SideRail).vm.$emit('change', 'sources')
  await flushPromises()
  wrapper.getComponent(SourceWorkspace).vm.$emit('graph')
  await flushPromises()
  wrapper.getComponent(KnowledgeEvolution).vm.$emit('compare', ['first', 'second'])
  await flushPromises()
  wrapper.getComponent(KnowledgeEvolution).vm.$emit('closeComparison')
  finish(detail('first'))
  await flushPromises()
  expect(wrapper.getComponent(KnowledgeEvolution).props('comparison')).toBeNull()
  const foreign = detail('first')
  foreign.entity.project_id = 'other-project'
  vi.mocked(api.getEntityDetail).mockResolvedValueOnce(foreign).mockResolvedValueOnce(detail('second'))
  wrapper.getComponent(KnowledgeEvolution).vm.$emit('compare', ['first', 'second'])
  await flushPromises()
  expect(wrapper.getComponent(KnowledgeEvolution).props('comparison')).toBeNull()
  expect(wrapper.getComponent(KnowledgeEvolution).props('comparisonError')).toBeTruthy()
})

it('discards an older candidate filter result and retains source-wide review totals', async () => {
  vi.mocked(api.listProjects).mockResolvedValue({ items: [project], total: 1, page: 1, page_size: 20 })
  vi.mocked(api.listSources).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  vi.mocked(api.listRepositories).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  vi.mocked(api.getSource).mockResolvedValue({ ...source, source_type: 'markdown' })
  vi.mocked(api.listSourceChunks).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  const empty = { items: [], total: 0, page: 1, page_size: 20 }
  vi.mocked(api.listCandidates).mockResolvedValueOnce(empty)
  vi.mocked(api.getExtraction).mockResolvedValue({ task: null, candidate_count: 3,
    review_counts: { pending: 3, confirmed: 0, rejected: 0 } })
  const wrapper = shallowMount(App, { global: { stubs: { SourceWorkspace: { template: '<div><slot name="reviews" /></div>' } } } })
  wrapper.getComponent(SideRail).vm.$emit('change', 'sources')
  await flushPromises()
  wrapper.getComponent(SourceWorkspace).vm.$emit('selectSource', source.id, null)
  await flushPromises()
  let finish!: (value: api.CandidateList) => void
  vi.mocked(api.listCandidates).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    .mockResolvedValueOnce(empty)
  wrapper.getComponent(CandidateReview).vm.$emit('filter', { status: 'pending', kind: '', query: 'old' })
  await flushPromises()
  const filters = { status: 'confirmed' as const, kind: 'entity' as const, query: 'new' }
  wrapper.getComponent(CandidateReview).vm.$emit('filter', filters)
  await flushPromises()
  finish({ ...empty, total: 30 })
  await flushPromises()
  expect(api.listCandidates).toHaveBeenLastCalledWith(project.id, source.id, 1, filters)
  expect(wrapper.getComponent(CandidateReview).props('candidates')?.total).toBe(0)
  expect(wrapper.getComponent(CandidateReview).props('extraction')?.review_counts?.pending).toBe(3)
})
