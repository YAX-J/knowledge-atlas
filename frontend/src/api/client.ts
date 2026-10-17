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

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init, headers, signal: init.signal ?? AbortSignal.timeout(30000),
  })
  if (!response.ok) {
    let payload: ApiErrorEnvelope = {}
    try {
      payload = (await response.json()) as ApiErrorEnvelope
    } catch {
      // A non-JSON upstream error still becomes a consistent client error.
    }
    throw new ApiError(response.status, payload)
  }

  return (await response.json()) as T
}

