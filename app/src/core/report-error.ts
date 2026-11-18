import { getAccessToken } from '@/core/auth/session'
import { apiBase, getAppVersion, platform } from '@/core/config'

// Gửi lỗi giao diện và lỗi gọi API về POST /api/v1/client-logs (QĐ-30). Gom theo lô, bỏ lỗi trùng
// trong 1 phút, tối đa 50 mục mỗi lần, không bao giờ gửi mật khẩu hay mã. Gửi lỗi mà hỏng thì im lặng bỏ qua.

export interface ClientLogInput {
  kind: 'ui' | 'api'
  level?: 'error' | 'warn'
  message: string
  apiPath?: string | null
  httpStatus?: number | null
  errorCode?: string | null
  requestId?: string | null
  stack?: string | null
}

// Thân theo backend/app/core/router.py ClientLogIn (agent kiến trúc chốt 18/11).
interface ClientLog {
  level: 'error' | 'warn' | 'info'
  kind: 'ui_error' | 'api_error'
  screen: string
  message: string
  detail: Record<string, string | number | null>
  app_version: string
  occurred_at: string
}

const BATCH_MAX = 50
const DEDUPE_MS = 60_000
const FLUSH_DELAY_MS = 3_000
const queue: ClientLog[] = []
const recent = new Map<string, number>()
let timer: ReturnType<typeof setTimeout> | null = null

// Che chuỗi giống mã, mật khẩu trước khi gửi đi.
export function redactSecrets(text: string): string {
  return text
    .replace(/(Bearer|Device)\s+[\w.~+/-]+=*/gi, '$1 ***')
    .replace(/("?(password|refresh_token|access_token|device_token)"?\s*[:=]\s*)"[^"]*"/gi, '$1"***"')
}

export function shouldSend(key: string, now = Date.now()): boolean {
  const last = recent.get(key)
  if (last !== undefined && now - last < DEDUPE_MS) return false
  recent.set(key, now)
  return true
}

export function reportClientLog(input: ClientLogInput): void {
  const message = redactSecrets(input.message).slice(0, 2000)
  if (!shouldSend(`${input.kind}|${input.apiPath ?? ''}|${input.httpStatus ?? ''}|${message}`)) return
  const version = getAppVersion()
  queue.push({
    level: input.level ?? 'error',
    kind: input.kind === 'api' ? 'api_error' : 'ui_error',
    screen: window.location.pathname.slice(0, 100),
    message,
    detail: {
      api_path: input.apiPath ?? null,
      http_status: input.httpStatus ?? null,
      error_code: input.errorCode ?? null,
      request_id: input.requestId ?? null,
      stack: input.stack ? redactSecrets(input.stack).slice(0, 8000) : null,
      platform,
      user_agent: navigator.userAgent.slice(0, 300),
    },
    app_version: `${version.name} (${version.code})`.slice(0, 40),
    occurred_at: new Date().toISOString(),
  })
  if (queue.length >= BATCH_MAX) void flushClientLogs()
  else if (!timer) timer = setTimeout(() => void flushClientLogs(), FLUSH_DELAY_MS)
}

export function reportUiError(error: unknown, where = 'ui'): void {
  const err = error instanceof Error ? error : new Error(String(error))
  reportClientLog({ kind: 'ui', message: `${where}: ${err.message}`, stack: err.stack ?? null })
}

export async function flushClientLogs(): Promise<void> {
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
  const logs = queue.splice(0, BATCH_MAX)
  if (logs.length === 0) return
  const token = getAccessToken()
  try {
    await fetch(`${apiBase}/client-logs`, {
      method: 'POST',
      keepalive: true,
      headers: {
        'Content-Type': 'application/json',
        'X-App-Version': String(getAppVersion().code),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ items: logs }),
    })
  } catch {
    // Mất mạng: bỏ lô này, không gửi lại để khỏi dồn.
  }
  if (queue.length > 0) timer = setTimeout(() => void flushClientLogs(), FLUSH_DELAY_MS)
}

export function installGlobalErrorReporting(): void {
  window.addEventListener('error', (event) => reportUiError(event.error ?? event.message, 'window'))
  window.addEventListener('unhandledrejection', (event) => reportUiError(event.reason, 'promise'))
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') void flushClientLogs()
  })
}
