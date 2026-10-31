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
