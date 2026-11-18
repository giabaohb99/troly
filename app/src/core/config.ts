import { App } from '@capacitor/app'
import { Capacitor } from '@capacitor/core'

// Trên điện thoại giao diện chạy ở https://localhost nên phải gọi thẳng tên miền api;
// trên trình duyệt (Vite) gọi đường tương đối, Vite chuyển tiếp /api sang máy chủ.
export const isNative = Capacitor.isNativePlatform()
export const platform: 'android' | 'web' = isNative ? 'android' : 'web'
export const apiOrigin = isNative ? (import.meta.env.VITE_API_ORIGIN ?? 'https://assistant.baohuynh.io.vn') : ''
export const apiBase = `${apiOrigin}/api/v1`

export interface AppVersion {
  code: number
  name: string
}

let cachedVersion: AppVersion = { code: 0, name: 'web' }
let cachedAppId = 'web'

// Đọc versionCode thật từ APK một lần lúc mở app (CI ghi versionCode vào build.gradle theo thẻ vX.Y.Z).
export async function loadAppVersion(): Promise<AppVersion> {
  if (!isNative) return cachedVersion
  try {
    const info = await App.getInfo()
    cachedVersion = { code: Number(info.build) || 0, name: info.version }
    cachedAppId = info.id
  } catch {
    // Giữ mặc định: không đọc được bản thì máy chủ coi như bản cũ nhất, vẫn gọi được /device/release.
  }
  return cachedVersion
}

export function getAppVersion(): AppVersion {
  return cachedVersion
}

// Gói đang chạy: bản chính thức vn.io.baohuynh.troly, bản thử thêm đuôi .debug (30 mục 3.2).
export function getAppId(): string {
  return cachedAppId
}

export function isDebugBuild(): boolean {
  return cachedAppId.endsWith('.debug')
}
