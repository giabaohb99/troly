import { setupWorker } from 'msw/browser'
import { handlers } from '@/mocks/handlers'

// Chỉ nạp ở chế độ `npm run dev:mock`. Mật khẩu giả: matkhau123.
export async function startMockApi() {
  const worker = setupWorker(...handlers)
  await worker.start({ onUnhandledRequest: 'bypass', quiet: true })
}
