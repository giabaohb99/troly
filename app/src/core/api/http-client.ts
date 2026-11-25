import { ApiError, NETWORK_ERROR_MESSAGE } from '@/core/api/api-error'
import { clearSession, getAccessToken, isAccessFresh, loadRefreshToken, saveTokens, type Tokens } from '@/core/auth/session'
import { apiBase, getAppVersion } from '@/core/config'
import { reportClientLog } from '@/core/report-error'

// Gọi API /api/v1. Máy chủ trả phong bì {success, message, data}; hàm ở đây bóc phong bì, trả data,
// lỗi thì ném ApiError có câu tiếng Việt và mã lỗi. Mã truy cập hết hạn thì làm mới một lần rồi gọi lại.

interface Envelope<T> {
  success: boolean
  message: string
  data: T
}

let refreshing: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = await loadRefreshToken()
  if (!refreshToken) return null
  let res: Response
  try {
    res = await fetch(`${apiBase}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-App-Version': String(getAppVersion().code) },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
  } catch {
    throw new ApiError(0, NETWORK_ERROR_MESSAGE, 'NETWORK')
  }
  const json = (await res.json().catch(() => null)) as Envelope<Tokens & { user: unknown }> | null
  if (res.ok && json?.success) {
    await saveTokens(json.data)
    return json.data.access_token
  }
  if (res.status === 401) {
    // Mã làm mới hỏng hoặc bị thu hồi: phải đăng nhập lại.
    await clearSession()
    return null
  }
  throw new ApiError(res.status, json?.message || `Lỗi máy chủ (${res.status})`, (json?.data as { code?: string } | undefined)?.code)
}

// Lấy mã truy cập còn hạn; gộp các lần làm mới đồng thời thành một.
export async function ensureAccessToken(force = false): Promise<string | null> {
  if (!force && isAccessFresh()) return getAccessToken()
  refreshing ??= refreshAccessToken().finally(() => {
    refreshing = null
  })
  return refreshing
}

export function buildHeaders(token: string | null, extra?: Record<string, string>): Record<string, string> {
  return {
    'X-App-Version': String(getAppVersion().code),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  }
}

export async function toApiError(res: Response, path: string): Promise<ApiError> {
  const json = (await res.json().catch(() => null)) as Envelope<{ code?: string; fields?: Record<string, string>; retry_after?: number } | null> | null
  const code = json?.data?.code ?? (res.status >= 500 ? 'INTERNAL_ERROR' : 'UNKNOWN')
  const error = new ApiError(res.status, json?.message || `Lỗi máy chủ (${res.status})`, code, res.headers.get('X-Request-ID'), json?.data?.fields ?? null)
  const retry = Number(json?.data?.retry_after ?? res.headers.get('Retry-After'))
  if (Number.isFinite(retry) && retry > 0) error.retryAfter = retry
  if (res.status >= 500 || res.status === 426) {
    reportClientLog({ kind: 'api', message: error.message, apiPath: path, httpStatus: res.status, errorCode: code, requestId: error.requestId })
  }
  return error
}

interface RequestOptions {
  auth?: boolean
  signal?: AbortSignal
}

async function request<T>(method: string, path: string, body?: unknown, options: RequestOptions = {}): Promise<T> {
  const auth = options.auth ?? true
  const send = async (token: string | null) => {
    try {
      return await fetch(`${apiBase}${path}`, {
        method,
        signal: options.signal,
        headers: buildHeaders(token, body === undefined ? { Accept: 'application/json' } : { Accept: 'application/json', 'Content-Type': 'application/json' }),
        body: body === undefined ? undefined : JSON.stringify(body),
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new ApiError(0, NETWORK_ERROR_MESSAGE, 'NETWORK')
    }
  }

  let token = auth ? await ensureAccessToken() : null
  let res = await send(token)
  if (auth && res.status === 401) {
    const error = await toApiError(res.clone(), path)
    if (error.code === 'AUTH_TOKEN_EXPIRED' || error.code === 'AUTH_REQUIRED') {
      token = await ensureAccessToken(true)
      if (token) res = await send(token)
    }
  }
  if (!res.ok) {
    const error = await toApiError(res, path)
    if (auth && res.status === 401) await clearSession()
    throw error
  }
  if (res.status === 204) return null as T
  const json = (await res.json().catch(() => null)) as Envelope<T> | null
  if (!json?.success) throw new ApiError(res.status, json?.message || 'Máy chủ trả dữ liệu lạ.', 'BAD_RESPONSE')
  return json.data
}

export const apiGet = <T>(path: string, options?: RequestOptions) => request<T>('GET', path, undefined, options)
export const apiPost = <T>(path: string, body: unknown = {}, options?: RequestOptions) => request<T>('POST', path, body, options)
export const apiPut = <T>(path: string, body: unknown) => request<T>('PUT', path, body)
export const apiPatch = <T>(path: string, body: unknown) => request<T>('PATCH', path, body)
export const apiDelete = <T>(path: string) => request<T>('DELETE', path)

// Dựng chuỗi truy vấn, bỏ giá trị rỗng.
export function toQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}
