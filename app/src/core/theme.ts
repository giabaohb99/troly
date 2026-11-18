import { isNative } from '@/core/config'
import { System } from '@/core/native/system'

// Giao diện Tối, Sáng, Theo máy (QĐ-37). Lưu trên máy; mặc định Theo máy. index.html đọc cùng khóa trước khi vẽ
// để không chớp màu lúc mở app.

export type ThemePref = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'troly.theme'
// Màu nền của từng giao diện cho thanh trạng thái, thanh điều hướng Android và thẻ meta theme-color
// (khớp --background trong index.css; Android không đọc được oklch).
const BAR_COLORS = { dark: '#0f1115', light: '#f8f9fb' } as const

let systemDark = typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches === true
const listeners = new Set<() => void>()

export function getThemePref(): ThemePref {
  const value = localStorage.getItem(STORAGE_KEY)
  return value === 'light' || value === 'dark' ? value : 'system'
}

export function isDarkTheme(pref: ThemePref = getThemePref()): boolean {
  return pref === 'dark' || (pref === 'system' && systemDark)
}

export function applyTheme(): void {
  const dark = isDarkTheme()
  document.documentElement.classList.toggle('dark', dark)
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
  const color = dark ? BAR_COLORS.dark : BAR_COLORS.light
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', color)
  if (isNative) void System.setBarStyle({ dark, color }).catch(() => undefined)
  listeners.forEach((listener) => listener())
}

export function setThemePref(pref: ThemePref): void {
  if (pref === 'system') localStorage.removeItem(STORAGE_KEY)
  else localStorage.setItem(STORAGE_KEY, pref)
  applyTheme()
}

export function subscribeTheme(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

// Gọi một lần lúc mở app: đọc chế độ tối của máy (trên Android hỏi lớp gốc cho chắc) và nghe khi máy đổi.
export async function initTheme(): Promise<void> {
  if (isNative) {
    try {
      systemDark = (await System.getSystemTheme()).dark
    } catch {
      // Giữ giá trị từ prefers-color-scheme.
    }
    void System.addListener('systemThemeChanged', ({ dark }: { dark: boolean }) => {
      systemDark = dark
      applyTheme()
    })
  } else {
    window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener('change', (event) => {
      systemDark = event.matches
      applyTheme()
    })
  }
  applyTheme()
}
