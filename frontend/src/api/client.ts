const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
).replace(/\/$/, '')

interface ApiErrorEnvelope {
  error?: {
    code?: string
    message?: string
    details?: unknown
    request_id?: string
  }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown
  readonly requestId?: string

  constructor(status: number, payload: ApiErrorEnvelope) {
    super(payload.error?.message ?? `请求失败（HTTP ${status}）`)
    this.name = 'ApiError'
    this.status = status
    this.code = payload.error?.code ?? 'HTTP_ERROR'
    this.details = payload.error?.details
    this.requestId = payload.error?.request_id
  }
}

function unavailable(init: RequestInit) {
  const write = !['GET', 'HEAD'].includes((init.method ?? 'GET').toUpperCase())
  return new ApiError(0, { error: {
    code: write ? 'REQUEST_RESULT_UNKNOWN' : 'READ_UNAVAILABLE',
    message: write ? '未能确认处理结果，服务端可能仍在执行。请先刷新状态，避免重复提交。' : '读取超时或网络不可用，请重试读取。',
  } })
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init, headers, signal: init.signal ?? AbortSignal.timeout(30000),
    })
  } catch (cause) {
    if (init.signal?.aborted && init.signal.reason?.name === 'AbortError') throw cause
    throw unavailable(init)
  }
  if (!response.ok) {
    let payload: ApiErrorEnvelope = {}
    try {
      payload = (await response.json()) as ApiErrorEnvelope
    } catch {
      // A non-JSON upstream error still becomes a consistent client error.
    }
    throw new ApiError(response.status, payload)
  }

  try {
    return (await response.json()) as T
  } catch {
    throw unavailable(init)
  }
}

