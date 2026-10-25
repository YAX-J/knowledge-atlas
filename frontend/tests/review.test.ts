import { afterEach, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import CandidateReview from '../src/components/CandidateReview.vue'
import type { KnowledgeCandidate } from '../src/types'
import { project } from './fixtures'

enableAutoUnmount(afterEach)
const candidate: KnowledgeCandidate = {
  id: 'candidate-1', project_id: project.id, source_id: 'source-1', task_id: 'task-1', kind: 'entity',
  type: 'Concept', name: 'Review', summary: 'Evidence is required.', confidence: .8, review_status: 'pending',
  knowledge_id: null, source_candidate_id: null, target_candidate_id: null,
  evidence: [{ chunk_id: 'chunk-1', quote: '<img src=x onerror=alert(1)>', start_line: 1, end_line: 1, heading_path: [] }],
  created_at: project.created_at, updated_at: project.updated_at,
}
const props = { candidates: { items: [candidate], total: 1, page: 1, page_size: 20 },
  extraction: null, loading: false, extracting: false, resolving: '', error: '', notice: '' }

it('requires an explicit confirm or reject and displays evidence as inert text', async () => {
  const wrapper = mount(CandidateReview, { props })
  expect(wrapper.find('img').exists()).toBe(false)
  expect(wrapper.get('blockquote').text()).toContain('<img')
  await wrapper.findAll('button').find(button => button.text() === '确认')!.trigger('click')
  await wrapper.findAll('button').find(button => button.text() === '拒绝')!.trigger('click')
  expect(wrapper.emitted('resolve')).toEqual([[{ id: candidate.id, action: 'confirm' }], [{ id: candidate.id, action: 'reject' }]])
})

it('edits before confirmation and trims explicit changes', async () => {
  const wrapper = mount(CandidateReview, { props })
  await wrapper.findAll('button').find(button => button.text() === '修改后确认')!.trigger('click')
  await wrapper.get('input[type="text"], input:not([type])').setValue('  Revised  ')
  await wrapper.get('textarea').setValue('  Revised evidence summary.  ')
  await wrapper.get('.candidate-card form').trigger('submit')
  expect(wrapper.emitted('resolve')).toEqual([[{ id: candidate.id, action: 'confirm',
    changes: { name: 'Revised', summary: 'Revised evidence summary.' } }]])
})

it('disables review and extraction controls during persistence', () => {
  const wrapper = mount(CandidateReview, { props: { ...props, resolving: candidate.id } })
  expect(wrapper.findAll('button').every(button => button.attributes('disabled') !== undefined)).toBe(true)
})

it('requires selection and a named preview before batch confirmation', async () => {
  const wrapper = mount(CandidateReview, { props })
  await wrapper.get('input[type="checkbox"]').setValue(true)
  await wrapper.findAll('button').find(button => button.text() === '审核所选')!.trigger('click')
  expect(wrapper.emitted('resolveBatch')).toBeUndefined()
  expect(wrapper.get('.batch-preview').text()).toContain('实体：Review')
  await wrapper.get('.batch-preview').trigger('submit')
  expect(wrapper.emitted('resolveBatch')).toEqual([[[candidate.id], 'confirm']])
})

it('submits review filters explicitly and clears an old selection when filters change', async () => {
  const wrapper = mount(CandidateReview, { props })
  await wrapper.get('input[type="checkbox"]').setValue(true)
  await wrapper.findAll('button').find(button => button.text() === '审核所选')!.trigger('click')
  await wrapper.get('select').setValue('pending')
  await wrapper.get('input[type="search"]').setValue('  Evidence  ')
  await wrapper.get('[aria-label="筛选候选"]').trigger('submit')
  expect(wrapper.emitted('filter')).toEqual([[{ status: 'pending', kind: '', query: 'Evidence' }]])
  await wrapper.setProps({ filters: { status: 'pending', kind: '', query: 'Evidence' } })
  expect(wrapper.find('.batch-preview').exists()).toBe(false)
  expect(wrapper.get('[aria-label="批量审核"]').text()).toContain('已选 0 条')
})

it('clears page selection and cannot submit an outdated preview', async () => {
  const wrapper = mount(CandidateReview, { props })
  await wrapper.get('input[type="checkbox"]').setValue(true)
  await wrapper.findAll('button').find(button => button.text() === '拒绝所选')!.trigger('click')
  await wrapper.setProps({ candidates: { ...props.candidates, page: 2, items: [{ ...candidate, id: 'second' }] } })
  expect(wrapper.find('.batch-preview').exists()).toBe(false)
  expect(wrapper.get('[aria-label="批量审核"]').text()).toContain('已选 0 条')
  expect(wrapper.emitted('resolveBatch')).toBeUndefined()
})

it('does not combine unsaved edits with batch decisions and unlocks after save', async () => {
  const second = { ...candidate, id: 'second' }
  const wrapper = mount(CandidateReview, { props: { ...props, candidates: { ...props.candidates, items: [candidate, second] } } })
  await wrapper.findAll('button').find(button => button.text() === '修改后确认')!.trigger('click')
  expect(wrapper.get('input[type="checkbox"]').attributes('disabled')).toBeDefined()
  await wrapper.setProps({ candidates: { ...props.candidates, items: [{ ...candidate, review_status: 'confirmed' }, second] } })
  expect(wrapper.get('input[type="checkbox"]').attributes('disabled')).toBeUndefined()
})
