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
    expect(wrapper.emitted('ask')).toEqual([['Where is the evidence?', 'hybrid']])
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
  it('shows stale content despite full index coverage and refreshes without rebuilding', async () => {
    const wrapper = mount(KnowledgeSearch, { props: { ...searchProps, indexStatus: {
      model: 'test-model', dimensions: 1024, configured: true, checked_at: project.created_at,
      eligible_count: 5, indexed_count: 5, missing_count: 0, stale_count: 2, current_count: 3,
      scanned_count: 5, scan_limit: 1000, truncated: false,
    } } })
    expect(wrapper.get('[aria-label="语义索引状态"]').text()).toContain('发现 2 条内容过期')
    await wrapper.findAll('button').find(button => button.text() === '刷新索引状态')!.trigger('click')
    expect(wrapper.emitted('inspectIndex')).toHaveLength(1)
    expect(wrapper.emitted('rebuild')).toBeUndefined()
    await wrapper.setProps({ indexStatus: { ...wrapper.props('indexStatus')!, stale_count: 0,
      scanned_count: 1, truncated: true, scan_limit: 1 } })
    expect(wrapper.text()).toContain('尚有知识未检查')
    expect(wrapper.text()).not.toContain('索引内容已与正式知识同步')
  })
  it('submits explicit BM25 mode without requesting a semantic index', async () => {
    const wrapper = mount(KnowledgeSearch, { props: searchProps })
    await wrapper.get('input').setValue('中文资料如何检索？')
    await wrapper.get('#project-search-mode').setValue('bm25')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('search')).toEqual([['中文资料如何检索？', '', 'bm25']])
    expect(wrapper.emitted('rebuild')).toBeUndefined()
    await wrapper.setProps({ result: { query: '中文资料如何检索？', mode: 'bm25', items: [],
      truncated: true, indexed_count: null, eligible_count: 2, weights: null,
      lexical: { protocol: 'mixed-bm25-v1', query_terms: ['中文'], scanned_count: 1,
        entity_limit: 1, text_limit_per_entity: 4000, truncated_reasons: ['entity_limit'] } } })
    expect(wrapper.text()).toContain('本地词法扫描 1/2')
    expect(wrapper.text()).toContain('部分排序文本或候选未参与计算')
    expect(wrapper.text()).not.toContain('语义索引尚未覆盖')
    expect(wrapper.text()).not.toContain('已索引')
  })
  it.each(['loading', 'rebuilding'] as const)('blocks form submission during %s', async busy => {
    const wrapper = mount(KnowledgeSearch, { props: { ...searchProps, [busy]: true } })
    await wrapper.get('input').setValue('query')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('search')).toBeUndefined()
  })
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
  it('submits source filters explicitly and distinguishes filtered empty results from an empty project', async () => {
    const wrapper = mount(SourceWorkspace, { props: { ...sourceProps,
      sourceFilters: { query: 'notes', type: 'markdown', status: 'failed' },
      sources: { items: [], total: 0, page: 1, page_size: 20 } } })
    expect(wrapper.text()).toContain('没有符合条件的资料')
    expect(wrapper.text()).toContain('已打开的资料不在本页结果中')
    expect(wrapper.text()).not.toContain('这个项目还没有资料')
    await wrapper.get('.source-filters input').setValue('  notes/decision  ')
    await wrapper.get('.source-filters').trigger('submit')
    expect(wrapper.emitted('filterSources')).toEqual([[{ query: 'notes/decision', type: 'markdown', status: 'failed' }]])
    await wrapper.findAll('button').find(button => button.text() === '重置资料筛选')!.trigger('click')
    expect(wrapper.emitted('filterSources')?.[1]).toEqual([{ query: '', type: '', status: '' }])
  })
  it('retries the failed source page rather than the previously displayed one', async () => {
    const wrapper = mount(SourceWorkspace, { props: { ...sourceProps, sourcesRequestedPage: 3,
      sources: { items: [], total: 50, page: 1, page_size: 20 }, errors: { ...errors, sources: 'Offline' } } })
    await wrapper.findAll('button').find(button => button.text() === '重试加载资料')!.trigger('click')
    expect(wrapper.emitted('sourcesPage')).toEqual([[3]])
  })
  it.each(['loading', 'review'] as const)('blocks source filter submission while %s is busy', async busy => {
    const wrapper = mount(SourceWorkspace, { props: { ...sourceProps,
      reviewBusy: busy === 'review', loading: { ...loading, sources: busy === 'loading' } } })
    await wrapper.get('.source-filters').trigger('submit')
    expect(wrapper.emitted('filterSources')).toBeUndefined()
  })
  it('locks source and upload controls while a review transaction is running', () => {
    const wrapper = mount(SourceWorkspace, { props: { ...sourceProps, reviewBusy: true } })
    expect(wrapper.findAll('button').find(button => button.text() === '上传单个文件')!.attributes('disabled')).toBeDefined()
    expect(wrapper.get('[aria-label="跨文件调用分析方式"]').attributes('disabled')).toBeDefined()
  })
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
