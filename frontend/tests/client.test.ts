import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiRequest } from '../src/api/client'
import { analyzeAgentCalls } from '../src/api/knowledgeAtlas'

afterEach(() => vi.unstubAllGlobals())
describe('API transport', () => {
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
