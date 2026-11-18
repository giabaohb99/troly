import { Secure } from '@/core/native/secure'

// Phiên đăng nhập: mã truy cập chỉ nằm trong bộ nhớ; mã làm mới (365 ngày, QĐ-27) cất qua plugin Secure.

export interface Tokens {
  access_token: string
  access_expires_at: string
  refresh_token: string
  refresh_expires_at: string
}

type Listener = (loggedIn: boolean) => void

let accessToken: string | null = null
let accessExpiresAt = 0
const listeners = new Set<Listener>()

export function getAccessToken(): string | null {
  return accessToken
}

// Còn dưới 60 giây thì coi như hết hạn để làm mới trước, tránh 401 giữa chừng.
export function isAccessFresh(now = Date.now()): boolean {
  return accessToken !== null && accessExpiresAt - now > 60_000
}

export async function saveTokens(tokens: Tokens): Promise<void> {
  accessToken = tokens.access_token
  accessExpiresAt = Date.parse(tokens.access_expires_at) || 0
  await Secure.set({ key: 'refresh_token', value: tokens.refresh_token })
  notify(true)
}

export async function loadRefreshToken(): Promise<string | null> {
  const { value } = await Secure.get({ key: 'refresh_token' })
  return value
}

export async function clearSession(): Promise<void> {
  accessToken = null
  accessExpiresAt = 0
  await Secure.clear()
  notify(false)
}

export function onSessionChange(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function notify(loggedIn: boolean) {
  for (const listener of listeners) listener(loggedIn)
}
