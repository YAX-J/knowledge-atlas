import { afterEach, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import AnswerClaims from '../src/components/AnswerClaims.vue'
import QuestionWorkspace from '../src/components/QuestionWorkspace.vue'
import { project, answerFixture } from './fixtures'

enableAutoUnmount(afterEach)

it.each(['evidence-claims-v2', 'evidence-claims-v3'] as const)('renders %s mixed support with exact citations in claim order',async(protocol)=>{
  const answer=answerFixture();answer.answer_protocol=protocol
  const wrapper=mount(AnswerClaims,{props:{answer}})
  expect(wrapper.findAll('.answer-claim')).toHaveLength(2)
  expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.text()).toContain('<script>Storage.</script>')
  expect(wrapper.text()).toContain('证据不足')
  expect(wrapper.text()).not.toContain(answer.answer)
  const buttons=wrapper.findAll('.claim-citations button')
  expect(buttons[0]!.text()).toContain('[2]')
  await buttons[0]!.trigger('click')
  expect(wrapper.emitted('openEvidence')).toEqual([[answer.evidence[1]]])
  expect(wrapper.findAll('.answer-claim')[1]!.find('button').exists()).toBe(false)
})

it('retains historical flat answers without inventing per-claim attribution',()=>{
  const answer=answerFixture();delete answer.claims;delete answer.answer_protocol
  const wrapper=mount(AnswerClaims,{props:{answer}})
  expect(wrapper.get('.answer-text').text()).toBe(answer.answer)
  expect(wrapper.text()).toContain('未保存逐条引用对应关系')
  expect(wrapper.find('.answer-claim').exists()).toBe(false)
})

it('shows unavailable citations without emitting a guessed source',()=>{
  const answer=answerFixture();answer.evidence=[]
  const wrapper=mount(AnswerClaims,{props:{answer}})
  expect(wrapper.text()).toContain('该引用暂不可定位')
  expect(wrapper.find('button').exists()).toBe(false)
  expect(wrapper.emitted('openEvidence')).toBeUndefined()
})

it('opens the exact saved relationship and its source from the cited claim', async () => {
  const answer = answerFixture()
  const evidence = answer.evidence[1]!
  evidence.relationship = {
    id: 'old-edge', type: 'USES', source: { id: 'orders', name: '订单服务' },
    target: { id: 'mysql', name: 'MySQL' }, valid_at: '2026-04-01T00:00:00Z',
    valid_from: '2026-03-01T00:00:00Z', valid_to: '2026-06-01T00:00:00Z',
  }
  const wrapper = mount(AnswerClaims, { props: { answer } })
  const details = wrapper.get('details')
  expect(details.get('summary').text()).toBe('[2] 查看支撑关系')
  expect(details.text()).toContain('订单服务 → MySQL')
  expect(details.findAll('time').map(value => value.attributes('datetime'))).toEqual([
    evidence.relationship.valid_at, evidence.relationship.valid_from, evidence.relationship.valid_to,
  ])
  await details.get('button').trigger('click')
  expect(wrapper.emitted('openEvidence')).toEqual([[evidence]])
})

it('shows the inferred instant and lets a reader override it before asking again', async () => {
  const answer = answerFixture()
  answer.time_scope = { source: 'question', valid_at: '2026-04-01T00:00:00Z', expression: '2026 年 4 月 1 日' }
  const wrapper = mount(QuestionWorkspace, { attachTo: document.body, props: {
    projects: null, project, projectsLoading: false, projectsError: '', result: answer, loading: false, error: '',
  } })
  const shown = wrapper.get('[aria-label="实际查询时点"]')
  expect(shown.text()).toContain('从问题识别')
  expect(shown.text()).toContain('2026 年 4 月 1 日')
  expect(shown.get('time').attributes('datetime')).toBe(answer.time_scope.valid_at)
  await wrapper.findAll('button').find(button => button.text() === '修改查询时点')!.trigger('click')
  const input = wrapper.get('#question-valid-at')
  expect(document.activeElement).toBe(input.element)
  expect(wrapper.get('textarea').element.value).toBe(answer.question)
  const chosen = '2026-06-01T08:00'
  await input.setValue(chosen)
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('ask')).toEqual([[answer.question, 'rrf', new Date(chosen).toISOString()]])
})

it('shows the two comparison times and opens the cited note for each side', async () => {
  const answer = answerFixture()
  const [before, after] = [answer.evidence[0]!, answer.evidence[1]!]
  const subject = { id: 'orders', name: '订单服务' }
  const earlier = '2026-04-01T00:00:00Z'
  const later = '2026-06-01T00:00:00Z'
  before.relationship = { id: 'old', type: 'USES', source: subject, target: { id: 'mysql', name: 'MySQL' },
    valid_at: earlier, valid_from: '2026-03-01T00:00:00Z', valid_to: later }
  after.relationship = { id: 'new', type: 'USES', source: subject, target: { id: 'pg', name: 'PostgreSQL' },
    valid_at: later, valid_from: later, valid_to: null }
  answer.time_scope = { source: 'comparison', valid_at: null }
  answer.comparison = { source: 'dates', before_at: earlier, after_at: later, cutover_at: later,
    before_citation_id: before.id, after_citation_id: after.id }
  answer.claims = [
    { text: '切换前的主数据库是 MySQL。', status: 'supported', citation_ids: [before.id] },
    { text: '切换后的主数据库是 PostgreSQL。', status: 'supported', citation_ids: [after.id] },
  ]
  const wrapper = mount(AnswerClaims, { props: { answer } })
  expect(wrapper.get('[aria-label="实际对比时点"]').findAll('time').map(time => time.attributes('datetime')))
    .toEqual([earlier, later, later])
  expect(wrapper.findAll('summary').map(summary => summary.text()))
    .toEqual(['[1] 查看切换前关系', '[2] 查看切换后关系'])
  for (const button of wrapper.findAll('.claim-citations button')) await button.trigger('click')
  expect(wrapper.emitted('openEvidence')).toEqual([[before], [after]])
})

it('offers a manual date when the question needs clarification', async () => {
  const answer = { ...answerFixture(), supported: false, time_scope: { source: 'clarification' as const, valid_at: null }, claims: [] }
  const wrapper = mount(QuestionWorkspace, { attachTo: document.body, props: {
    projects: null, project, projectsLoading: false, projectsError: '', result: answer, loading: false, error: '',
  } })
  expect(wrapper.text()).toContain('请选择查询时点')
  expect(wrapper.find('[aria-label="实际查询时点"]').exists()).toBe(false)
  await wrapper.findAll('button').find(button => button.text() === '手动选择时点')!.trigger('click')
  expect(document.activeElement).toBe(wrapper.get('#question-valid-at').element)
})

it('forwards per-claim navigation from the shared question/conversation workspace',async()=>{
  const answer=answerFixture()
  const wrapper=mount(QuestionWorkspace,{props:{projects:null,project,projectsLoading:false,projectsError:'',
    result:answer,loading:false,error:'',persistent:true}})
  expect(wrapper.text()).toContain('部分结论有引用')
  expect(wrapper.text()).toContain('Benchmark evidence.')
  await wrapper.get('.claim-citations button').trigger('click')
  expect(wrapper.emitted('openEvidence')).toEqual([[answer.evidence[1]]])
  await wrapper.setProps({result:{...answer,supported:true,claims:answer.claims!.slice(0,1)}})
  expect(wrapper.text()).not.toContain('部分结论有引用')
  await wrapper.setProps({result:{...answer,claims:answer.claims!.slice(1),evidence:[]}})
  expect(wrapper.text()).toContain('暂不能确认')
})
