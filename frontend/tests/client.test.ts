import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiRequest } from '../src/api/client'
import { analyzeAgentCalls, askQuestion, listSources, searchKnowledge } from '../src/api/knowledgeAtlas'

afterEach(() => vi.unstubAllGlobals())
describe('API transport', () => {
  it('uses longer bounded budgets for vector search, answers and multi-turn analysis', async () => {
    const budgets: number[] = []
    const timeout = vi.spyOn(AbortSignal, 'timeout').mockImplementation(milliseconds => {
      budgets.push(milliseconds)
      return new AbortController().signal
    })
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response('{}'))))
    try {
      await searchKnowledge('project', 'query', '', 'bm25')
      await searchKnowledge('project', 'query', '', 'vector')
      await askQuestion('project', 'query', 'bm25_source')
      await analyzeAgentCalls('source', 'tools')
      expect(budgets).toEqual([30_000, 240_000, 420_000, 900_000])
    } finally { timeout.mockRestore() }
  })
  it('distinguishes uncertain writes from retryable read failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('Timed out', 'TimeoutError')))
    await expect(apiRequest('/write', { method: 'POST' })).rejects.toMatchObject({ code: 'REQUEST_RESULT_UNKNOWN' })
    await expect(apiRequest('/read')).rejects.toMatchObject({ code: 'READ_UNAVAILABLE' })
  })
  it('encodes source filters without treating query punctuation as URL syntax', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('{}'))
    vi.stubGlobal('fetch', fetcher)
    await listSources('project-1', 2, 20, { query: '  docs/a&b_100%  ', type: 'markdown', status: 'failed' })
    const query = new URL(String(fetcher.mock.calls[0]?.[0]), 'http://localhost').searchParams
    expect(query.get('q')).toBe('docs/a&b_100%')
    expect(query.get('source_type')).toBe('markdown')
    expect(query.get('source_status')).toBe('failed')
    expect(query.get('page')).toBe('2')
  })
  it('preserves structured error and request identity', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'MODEL_UNAVAILABLE', message: 'Unavailable', details: { retry: false }, request_id: 'req-1' },
    }), { status: 503 })))
    await expect(apiRequest('/test')).rejects.toMatchObject({ status: 503, code: 'MODEL_UNAVAILABLE', requestId: 'req-1' })
  })
  it('normalizes a non-JSON upstream error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>bad gateway</html>', { status: 502 })))
    await expect(apiRequest('/test')).rejects.toBeInstanceOf(ApiError)
    await expect(apiRequest('/test')).rejects.toMatchObject({ code: 'HTTP_ERROR', status: 502 })
  })
  it('keeps caller cancellation and uses JSON headers only for JSON bodies', async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}')))
    vi.stubGlobal('fetch', fetcher)
    const signal = new AbortController().signal
    await apiRequest('/test', { method: 'POST', body: '{}', signal })
    expect(fetcher.mock.calls[0]?.[1].signal).toBe(signal)
    expect(fetcher.mock.calls[0]?.[1].headers.get('Content-Type')).toBe('application/json')
    await apiRequest('/test', { method: 'POST', body: new FormData() })
    expect(fetcher.mock.calls[1]?.[1].headers.has('Content-Type')).toBe(false)
  })
  it('explicitly sends tools strategy without silently changing the default', async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}')))
    vi.stubGlobal('fetch', fetcher)
    await analyzeAgentCalls('source-1', 'tools')
    await analyzeAgentCalls('source-1')
    expect(fetcher.mock.calls[0]?.[0]).toContain('strategy=tools')
    expect(fetcher.mock.calls[1]?.[0]).toContain('strategy=single_step')
  })
})
