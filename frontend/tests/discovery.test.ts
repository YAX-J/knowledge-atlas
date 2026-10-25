import { afterEach, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import KnowledgeComparison from '../src/components/KnowledgeComparison.vue'
import KnowledgeEvolution from '../src/components/KnowledgeEvolution.vue'
import QuestionWorkspace from '../src/components/QuestionWorkspace.vue'
import type { EntityDetail, QuestionAnswer } from '../src/types'
import { project } from './fixtures'

enableAutoUnmount(afterEach)

export function detail(id: string): EntityDetail {
  return { entity: { id, project_id: project.id, candidate_id: `candidate-${id}`, type: 'Decision',
    name: 'Storage decision', summary: `Summary ${id}`, confidence: .8, status: 'active',
    valid_from: project.created_at, valid_to: null, evidence_count: 1 },
    evidence: [{ id: `evidence-${id}`, source_id: `source-${id}`, chunk_id: `chunk-${id}`,
      title: `${id}.md`, uri: `project://source-${id}`, git_url: null, quote: '<script>Original text</script>',
      start_line: 2, end_line: 2, heading_path: [] }], relationships: [], truncated: false }
}

it('compares equal names using separate source evidence and emits exact locators', async () => {
  const first = detail('first'), second = detail('second')
  const wrapper = mount(KnowledgeComparison, { props: { details: [first, second], loading: false, error: '', busy: false } })
  expect(wrapper.findAll('.comparison-columns > article')).toHaveLength(2)
  expect(wrapper.text()).toContain('first.md')
  expect(wrapper.text()).toContain('second.md')
  expect(wrapper.find('script').exists()).toBe(false)
  await wrapper.findAll('button').find(button => button.text() === '核对原文分块')!.trigger('click')
  expect(wrapper.emitted('openEvidence')).toEqual([[first.evidence[0]]])
  await wrapper.findAll('button').find(button => button.text() === '关闭核对')!.trigger('click')
  expect(wrapper.emitted('close')).toHaveLength(1)
})

it('provides retry for failed comparison without showing old details', async () => {
  const wrapper = mount(KnowledgeComparison, { props: { details: null, loading: false, error: 'Read failed', busy: false } })
  expect(wrapper.find('.comparison-columns').exists()).toBe(false)
  await wrapper.get('[role="alert"] button').trigger('click')
  expect(wrapper.emitted('retry')).toHaveLength(1)
})

it('requests a governance category and compares a two-entity finding', async () => {
  const wrapper = mount(KnowledgeEvolution, { props: {
    nodes: [], selected: null, history: null, changes: null,
    governance: { checked_at: project.created_at, scanned_entity_count: 2, truncated: false,
      counts_by_kind: { duplicate: 1, orphan: 2 },
      findings: [{ id: 'finding', kind: 'duplicate', entity_ids: ['first', 'second'], message: 'Duplicate' }] },
    historyLoading: false, changesLoading: false, governanceLoading: false,
    historyError: '', changesError: '', governanceError: '', actionError: '', notice: '', busy: false, historical: false,
  } })
  await wrapper.get('.governance select').setValue('duplicate')
  expect(wrapper.emitted('inspect')).toEqual([['duplicate']])
  await wrapper.findAll('button').find(button => button.text() === '并排核对两条知识')!.trigger('click')
  expect(wrapper.emitted('compare')).toEqual([[['first', 'second']]])
})

it('shows additional entity attribution once without repeating the cited passage', async () => {
  const first = detail('first'), second = detail('second')
  const result: QuestionAnswer = { id: 'answer', question: 'Storage?', supported: true, answer: 'Database.',
    confidence: .8, entity_ids: [first.entity.id], missing_information: [],
    evidence: [{ ...first.evidence[0]!, entity_id: first.entity.id, entity_name: first.entity.name,
      related_entities: [{ id: first.entity.id, name: first.entity.name }, { id: second.entity.id, name: second.entity.name }] }],
    retrieval: { keyword_hits: 0, vector_hits: 2, graph_hits: 0, indexed_count: 2, eligible_count: 2 } }
  const wrapper = mount(QuestionWorkspace, { props: { projects: null, project, projectsLoading: false,
    projectsError: '', result, loading: false, error: '' } })
  expect(wrapper.findAll('.evidence-card')).toHaveLength(1)
  await wrapper.get('.related-evidence-entities button').trigger('click')
  expect(wrapper.emitted('openEntity')).toEqual([['second']])
})
