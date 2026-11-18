import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@/index.css'
import { App } from '@/app/app'
import { loadAppVersion } from '@/core/config'
import { initTheme } from '@/core/theme'
import { installGlobalErrorReporting } from '@/core/report-error'

installGlobalErrorReporting()

async function start() {
  // Chế độ API giả (npm run dev:mock): MSW chặn /api trong trình duyệt.
  if (import.meta.env.MODE === 'mock') {
    const { startMockApi } = await import('@/mocks/browser')
    await startMockApi()
  }
  await loadAppVersion()
  await initTheme()
  const root = document.getElementById('root')
  if (!root) throw new Error('Thiếu thẻ #root trong index.html')
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

void start()
