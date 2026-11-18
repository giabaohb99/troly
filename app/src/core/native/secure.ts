import { registerPlugin, WebPlugin } from '@capacitor/core'

// Cất mã làm mới và mã thiết bị. Trên Android: plugin Kotlin SecurePlugin mã hóa bằng khóa trong
// AndroidKeyStore (30-app-android.md mục 3.5). Trên trình duyệt (chỉ để phát triển): localStorage.
export interface SecurePlugin {
  get(options: { key: SecureKey }): Promise<{ value: string | null }>
  set(options: { key: SecureKey; value: string }): Promise<void>
  remove(options: { key: SecureKey }): Promise<void>
  clear(): Promise<void>
}

export type SecureKey = 'refresh_token' | 'device_token'

const PREFIX = 'troly.secure.'

class SecureWeb extends WebPlugin implements SecurePlugin {
  async get({ key }: { key: SecureKey }) {
    return { value: localStorage.getItem(PREFIX + key) }
  }

  async set({ key, value }: { key: SecureKey; value: string }) {
    localStorage.setItem(PREFIX + key, value)
  }

  async remove({ key }: { key: SecureKey }) {
    localStorage.removeItem(PREFIX + key)
  }

  async clear() {
    for (const key of ['refresh_token', 'device_token'] as const) localStorage.removeItem(PREFIX + key)
  }
}

export const Secure = registerPlugin<SecurePlugin>('Secure', { web: () => new SecureWeb() })
