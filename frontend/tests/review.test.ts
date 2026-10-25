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

function relation(endpoints: KnowledgeCandidate['endpoints']): KnowledgeCandidate {
  return { ...candidate, id: 'relation', kind: 'relation', type: 'USES', name: 'Uses knowledge',
    source_candidate_id: candidate.id, target_candidate_id: 'second', endpoints }
}
const endpoint = (id: string, review_status: 'pending' | 'confirmed' | 'rejected') => ({ id, name: `Endpoint ${id}`, review_status })

it('shows filtered-out endpoint states and blocks confirmation while preserving rejection and entity navigation', async () => {
  const item = relation([endpoint(candidate.id, 'confirmed'), endpoint('second', 'pending')])
  const wrapper = mount(CandidateReview, { props: { ...props, candidates: { ...props.candidates, items: [item] } } })
  expect(wrapper.get('.relation-dependencies').text()).toContain('Endpoint second · 待确认')
  expect(wrapper.findAll('button').find(button => button.text() === '确认')!.attributes('disabled')).toBeDefined()
  expect(wrapper.findAll('button').find(button => button.text() === '修改后确认')!.attributes('disabled')).toBeDefined()
  await wrapper.findAll('button').find(button => button.text() === '查看本资料实体候选')!.trigger('click')
  expect(wrapper.emitted('filter')).toEqual([[{ status: '', kind: 'entity', query: '' }]])
  await wrapper.findAll('button').find(button => button.text() === '拒绝')!.trigger('click')
  expect(wrapper.emitted('resolve')).toEqual([[{ id: item.id, action: 'reject' }]])
})

it('allows a relation once both endpoints are confirmed and renders names as text', async () => {
  const item = relation([endpoint(candidate.id, 'confirmed'), { ...endpoint('second', 'confirmed'), name: '<img src=x onerror=alert(1)>' }])
  const wrapper = mount(CandidateReview, { props: { ...props, candidates: { ...props.candidates, items: [item] } } })
  expect(wrapper.find('img').exists()).toBe(false)
  const button = wrapper.findAll('button').find(button => button.text() === '确认')!
  expect(button.attributes('disabled')).toBeUndefined()
  await button.trigger('click')
  expect(wrapper.emitted('resolve')).toEqual([[{ id: item.id, action: 'confirm' }]])
})

it('does not implicitly select pending endpoints and validates the final batch submit', async () => {
  const item = relation([endpoint(candidate.id, 'pending'), endpoint('second', 'confirmed')])
  const wrapper = mount(CandidateReview, { props: { ...props, candidates: { ...props.candidates, items: [candidate, item] } } })
  await wrapper.get('input[aria-label="选择候选：Uses knowledge"]').setValue(true)
  await wrapper.findAll('button').find(button => button.text() === '审核所选')!.trigger('click')
  expect(wrapper.get('.batch-preview').text()).toContain('Endpoint candidate-1（待确认）')
  expect(wrapper.get('.batch-preview button[type="submit"]').attributes('disabled')).toBeDefined()
  await wrapper.get('.batch-preview').trigger('submit')
  expect(wrapper.emitted('resolveBatch')).toBeUndefined()
  expect(wrapper.get<HTMLInputElement>('input[aria-label="选择候选：Review"]').element.checked).toBe(false)
  await wrapper.get('input[aria-label="选择候选：Review"]').setValue(true)
  await wrapper.findAll('button').find(button => button.text() === '审核所选')!.trigger('click')
  expect(wrapper.find('.batch-preview .dependency-warning').exists()).toBe(false)
  await wrapper.get('.batch-preview').trigger('submit')
  expect(wrapper.emitted('resolveBatch')).toEqual([[['relation', candidate.id], 'confirm']])
})

it.each(['rejected', 'missing'] as const)('blocks %s endpoints but still permits explicit batch rejection', async state => {
  const item = relation(state === 'missing' ? [] : [endpoint(candidate.id, 'confirmed'), endpoint('second', 'rejected')])
  const wrapper = mount(CandidateReview, { props: { ...props, candidates: { ...props.candidates, items: [item] } } })
  expect(wrapper.get('.relation-dependencies').text()).toContain(state === 'missing' ? '状态不可用' : '已拒绝，无法确认关系')
  await wrapper.get('input[type="checkbox"]').setValue(true)
  await wrapper.findAll('button').find(button => button.text() === '拒绝所选')!.trigger('click')
  await wrapper.get('.batch-preview').trigger('submit')
  expect(wrapper.emitted('resolveBatch')).toEqual([[['relation'], 'reject']])
})
