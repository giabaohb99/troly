import { apiGet, apiPost, ensureAccessToken } from '@/core/api/http-client'
import { clearSession, saveTokens, type Tokens } from '@/core/auth/session'
import { getAppVersion, isNative } from '@/core/config'
import { Secure } from '@/core/native/secure'

export interface User {
  id: number
  name: string
  email: string
  timezone: string
}

export async function login(email: string, password: string): Promise<User> {
  const data = await apiPost<Tokens & { user: User }>('/auth/login', { email, password, label: describeDevice().name }, { auth: false })
  await saveTokens(data)
  void registerDeviceOnce()
  return data.user
}

// Chưa có mã làm mới thì trả null, không gọi máy chủ.
export async function fetchMe(): Promise<User | null> {
  const token = await ensureAccessToken()
  if (!token) return null
  return apiGet<User>('/auth/me')
}

export async function logout(): Promise<void> {
  try {
    await apiPost('/auth/logout')
  } finally {
    await clearSession()
  }
}

// Đọc đời máy từ user agent của WebView, ví dụ "Android 15; SM-S936B".
export function describeDevice(userAgent = navigator.userAgent) {
  const android = userAgent.match(/Android\s+([\d.]+);\s*([^;)]+)/)
  const model = android ? android[2].replace(/\s+Build.*$/, '').trim() : 'Trình duyệt'
  const manufacturer = /^SM-|samsung/i.test(model) ? 'samsung' : android ? 'android' : 'web'
  const name = /^SM-S93/.test(model) ? 'Galaxy S25+' : android ? model : 'Trình duyệt'
  return { name, model, manufacturer, osVersion: android ? `Android ${android[1]}` : 'web' }
}

// Đăng ký điện thoại một lần sau lần đăng nhập đầu; mã thiết bị trả một lần, cất qua plugin Secure
// cho plugin nghe thông báo dùng ở Phase 2 (30-app-android.md mục 3.5). Lỗi thì lần đăng nhập sau thử lại.
async function registerDeviceOnce(): Promise<void> {
  if (!isNative) return
  const { value } = await Secure.get({ key: 'device_token' })
  if (value) return
  const device = describeDevice()
  const version = getAppVersion()
  try {
    const data = await apiPost<{ device: unknown; device_token: string }>('/devices', {
      name: device.name,
      model: device.model,
      manufacturer: device.manufacturer,
      os_version: device.osVersion,
      app_version_code: version.code,
      app_version_name: version.name,
    })
    await Secure.set({ key: 'device_token', value: data.device_token })
  } catch {
    // Không chặn đăng nhập.
  }
}
