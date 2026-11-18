import { lazy, type ComponentType } from 'react'

const RELOAD_KEY = 'troly-lazy-reload-at'

// Tải màn theo nhu cầu. Tệp màn không tải được (bản cũ còn trong bộ nhớ đệm) thì tải lại trang một lần;
// chặn vòng lặp: 30 giây mới cho tải lại một lần.
export function lazyPage<T extends ComponentType>(load: () => Promise<T>) {
  return lazy(async () => {
    try {
      return { default: await load() }
    } catch (error) {
      const last = Number(sessionStorage.getItem(RELOAD_KEY) ?? 0)
      if (Date.now() - last > 30_000) {
        sessionStorage.setItem(RELOAD_KEY, String(Date.now()))
        window.location.reload()
        return new Promise<never>(() => {})
      }
      throw error
    }
  })
}
