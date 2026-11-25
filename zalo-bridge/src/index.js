// Khởi động zalo-bridge: đọc cấu hình, nạp hàng đợi, đăng nhập lại bằng phiên đã lưu, mở HTTP nội bộ.
import { Zalo } from 'zca-js'
import { loadConfig } from './config.js'
import { EventQueue } from './event-queue.js'
import { createApp } from './http.js'
import { log, setLogLevel } from './log.js'
import { SessionStore } from './session-store.js'
import { ZaloService } from './zalo-service.js'

const config = loadConfig()
setLogLevel(config.logLevel)

const queue = new EventQueue({ dataDir: config.dataDir, eventsUrl: config.eventsUrl, token: config.token })
await queue.load()
const store = new SessionStore(config.dataDir, config.sessionKey)
const service = new ZaloService({ ZaloClass: Zalo, store, queue, config })

const server = createApp({ service, queue, token: config.token })
server.listen(config.port, () => log.info('zalo-bridge chạy', { port: config.port, queue_size: queue.size }))
if (queue.size) queue.schedule(0)
service.init().catch((err) => log.error('Khởi động phiên Zalo lỗi', { error: err.message }))

function shutdown() {
  log.info('Nhận tín hiệu dừng')
  try { service.api?.listener.stop() } catch { /* bỏ qua */ }
  queue.stop()
  server.close(() => process.exit(0))
  setTimeout(() => process.exit(0), 5_000).unref()
}
process.on('SIGTERM', shutdown)
process.on('SIGINT', shutdown)
