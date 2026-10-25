import { afterEach, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import CandidateReview from '../src/components/CandidateReview.vue'
import QuestionWorkspace from '../src/components/QuestionWorkspace.vue'
import KnowledgeEvolution from '../src/components/KnowledgeEvolution.vue'
import { project } from './fixtures'

enableAutoUnmount(afterEach)

it('shows source-wide review counts even when only one page is visible', () => {
  const wrapper = mount(CandidateReview, { props: {
    candidates: { items: [], total: 42, page: 2, page_size: 20 },
    extraction: { task: null, candidate_count: 42, review_counts: { pending: 22, confirmed: 15, rejected: 5 } },
    loading: false, extracting: false, resolving: '', error: '', notice: '',
  } })
  expect(wrapper.get('.review-progress').text()).toContain('待审核 22 · 已确认 15 · 已拒绝 5')
  expect(wrapper.text()).toContain('查看图谱与检索')
})

it('selects RRF for evidence questions and allows stopping the wait', async () => {
  const wrapper = mount(QuestionWorkspace, { props: {
    projects: null, project, projectsLoading: false, projectsError: '', result: null, loading: false, error: '',
  } })
  await wrapper.get('textarea').setValue('Why this database?')
  await wrapper.get('#question-retrieval-mode').setValue('rrf')
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('ask')).toEqual([['Why this database?', 'rrf']])
  await wrapper.setProps({ loading: true })
  await wrapper.findAll('button').find(item => item.text() === '停止等待')!.trigger('click')
  expect(wrapper.emitted('clear')).toHaveLength(1)
  expect(wrapper.text()).toContain('不会撤销服务端已发出的模型请求')
})

it('shows governance context outside the visible graph and opens evidence review', async () => {
  const wrapper = mount(KnowledgeEvolution, { props: {
    nodes: [], selected: null, history: null, changes: null,
    governance: { checked_at: project.created_at, scanned_entity_count: 2, truncated: false,
      findings: [{ id: 'finding', kind: 'duplicate', entity_ids: ['outside'], message: 'Check duplicate',
        entities: [{ id: 'outside', name: 'Off-canvas decision', summary: '<script>Summary</script>', type: 'Decision' }] }] },
    historyLoading: false, changesLoading: false, governanceLoading: false,
    historyError: '', changesError: '', governanceError: '', actionError: '', notice: '', busy: false, historical: false,
  } })
  expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.get('.findings').text()).toContain('Off-canvas decision')
  await wrapper.get('.findings button').trigger('click')
  expect(wrapper.emitted('openEntity')).toEqual([['outside']])
})
