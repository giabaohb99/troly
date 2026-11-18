import { App } from '@capacitor/app'
import { isNative } from '@/core/config'

// App có đang ở màn hình không: để biết lượt chat xong lúc chạy nền thì tự báo (QĐ-41).
let active = true
const listeners = new Set<(active: boolean) => void>()

if (isNative) {
  void App.addListener('appStateChange', ({ isActive }) => {
    active = isActive
    listeners.forEach((listener) => listener(isActive))
  })
} else if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    active = document.visibilityState === 'visible'
    listeners.forEach((listener) => listener(active))
  })
}

export function isAppActive(): boolean {
  return active
}

export function onAppActiveChange(listener: (active: boolean) => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
