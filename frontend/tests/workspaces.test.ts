import { afterEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import QuestionWorkspace from '../src/components/QuestionWorkspace.vue'
import KnowledgeSearch from '../src/components/KnowledgeSearch.vue'
import SourceWorkspace from '../src/components/SourceWorkspace.vue'
import { errors, loading, project, source } from './fixtures'

enableAutoUnmount(afterEach)
const questionProps = { projects: { items: [project], total: 1, page: 1, page_size: 20 }, project,
  projectsLoading: false, projectsError: '', result: null, loading: false, error: '' }
const searchProps = { result: null, loading: false, error: '', errorAction: 'search' as const,
  labels: { Concept: '概念' }, rebuilding: false, notice: '' }
const sourceProps = { view: 'sources' as const, projects: null, project, repositories: null, sources: null,
  selectedSourceId: source.id, source, task: null, chunks: null, agentCallAnalysis: null,
  codeStructure: { source_id: source.id, language: 'python', has_syntax_errors: false,
    symbols: [], calls: [], related_types: [], related_methods: [], type_relationships: [], cross_file_calls: [], truncated: false },
  loading, errors, notice: '' }

describe('evidence questions', () => {
  it('trims a submitted question and clears input when project changes', async () => {
    const wrapper = mount(QuestionWorkspace, { props: questionProps })
    await wrapper.get('textarea').setValue('  Where is the evidence?  ')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('ask')).toEqual([['Where is the evidence?']])
    await wrapper.setProps({ project: { ...project, id: 'project-2' } })
    expect(wrapper.get('textarea').element.value).toBe('')
  })
  it('blocks submission without project or during a request', async () => {
    const wrapper = mount(QuestionWorkspace, { props: { ...questionProps, project: null } })
    await wrapper.get('textarea').setValue('Question')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('ask')).toBeUndefined()
    await wrapper.setProps({ project, loading: true })
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('ask')).toBeUndefined()
  })
  it('exposes error retry and renders provider text without HTML', async () => {
    const wrapper = mount(QuestionWorkspace, { props: { ...questionProps, error: '<script>untrusted</script>' } })
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.get('[role="alert"]').text()).toContain('<script>')
    await wrapper.get('[role="alert"] button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })
})

describe('knowledge search', () => {
  it('emits trimmed query, type and explicit retrieval mode; clear resets all', async () => {
    const wrapper = mount(KnowledgeSearch, { props: searchProps })
    await wrapper.get('input').setValue('  PostgreSQL  ')
    await wrapper.get('#project-search-mode').setValue('hybrid')
    await wrapper.get('#project-search-type').setValue('Concept')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('search')).toEqual([['PostgreSQL', 'Concept', 'hybrid']])
    await wrapper.findAll('button').find(button => button.text() === '清空搜索')!.trigger('click')
    expect(wrapper.emitted('clear')).toHaveLength(1)
    expect(wrapper.get('input').element.value).toBe('')
    expect(wrapper.get<HTMLSelectElement>('#project-search-mode').element.value).toBe('keyword')
  })
  it('retries the failed operation rather than changing it', async () => {
    const wrapper = mount(KnowledgeSearch, { props: { ...searchProps, errorAction: 'rebuild', error: 'offline' } })
    await wrapper.get('[role="alert"] button').trigger('click')
    expect(wrapper.emitted('rebuild')).toHaveLength(1)
    expect(wrapper.emitted('retry')).toBeUndefined()
  })
})

describe('cross-file Agent workspace', () => {
  it('uses user-selected strategy for start and error retry', async () => {
    const wrapper = mount(SourceWorkspace, { props: sourceProps })
    await wrapper.get('[aria-label="跨文件调用分析方式"]').setValue('tools')
    await wrapper.findAll('button').find(button => button.text() === 'Agent 分析跨文件调用')!.trigger('click')
    expect(wrapper.emitted('analyzeCalls')).toEqual([['tools']])
    await wrapper.setProps({ errors: { ...errors, agent: 'Timed out' } })
    await wrapper.findAll('button').find(button => button.text() === '重试分析')!.trigger('click')
    expect(wrapper.emitted('analyzeCalls')).toEqual([['tools'], ['tools']])
  })
  it('locks strategy and context while Agent is running', () => {
    const wrapper = mount(SourceWorkspace, { props: { ...sourceProps, loading: { ...loading, agent: true } } })
    expect(wrapper.get('[aria-label="跨文件调用分析方式"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Agent 分析中')
  })
  it('shows empty analysis and sanitized tool trace as text', () => {
    const wrapper = mount(SourceWorkspace, { props: { ...sourceProps, agentCallAnalysis: {
      source_id: source.id, language: 'python', model: 'test', prompt_version: 'test', detected_call_count: 0,
      strategy: 'tools', scanned_source_count: 1, candidate_call_count: 0, provider_call_count: 0,
      related_symbols: [], calls: [], truncated: false, has_syntax_errors: false, tool_call_count: 1,
      tool_trace: [{ name: '<script>untrusted</script>', status: 'error', duration_ms: 0, result_characters: 0 }],
    } } })
    expect(wrapper.text()).toContain('本次未调用模型')
    expect(wrapper.get('.agent-tool-trace').text()).toContain('参数或范围被拒绝')
    expect(wrapper.find('script').exists()).toBe(false)
  })
})
