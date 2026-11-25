// Hàng đợi sự kiện gửi sang api troly: lưu trên /data, gửi theo lô, api tắt thì giữ lại và thử lại giãn dần.
import { mkdir, readFile, rename, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { log } from './log.js'

const MAX_EVENTS = 5000
// Trần của api cho một lần POST: 100 sự kiện, 1 MB (để dư cho phần bọc).
const BATCH = 100
const MAX_BATCH_BYTES = 900 * 1024
const MIN_DELAY_MS = 5_000
const MAX_DELAY_MS = 300_000

export class EventQueue {
  constructor({ dataDir, eventsUrl, token, fetchImpl = fetch, setTimer = setTimeout, clearTimer = clearTimeout }) {
    this.file = path.join(dataDir, 'events.json')
    this.eventsUrl = eventsUrl
    this.token = token
    this.fetch = fetchImpl
    this.setTimer = setTimer
    this.clearTimer = clearTimer
    this.items = []
    this.delay = MIN_DELAY_MS
    this.timer = null
    this.sending = false
    // api trả 401 (sai khóa): dừng gửi tới khi khởi động lại, không thử mãi.
    this.halted = false
  }

  get size() {
    return this.items.length
  }

  async load() {
    try {
      this.items = JSON.parse(await readFile(this.file, 'utf8'))
    } catch (err) {
      if (err.code !== 'ENOENT') log.warn('Không đọc được hàng đợi sự kiện, bắt đầu rỗng', { error: err.message })
      this.items = []
    }
  }

  async persist() {
    await mkdir(path.dirname(this.file), { recursive: true })
    const tmp = this.file + '.tmp'
    await writeFile(tmp, JSON.stringify(this.items), { mode: 0o600 })
    await rename(tmp, this.file)
  }

  async push(event) {
    this.items.push(event)
    if (this.items.length > MAX_EVENTS) {
      const dropped = this.items.length - MAX_EVENTS
      this.items.splice(0, dropped)
      log.warn('Hàng đợi sự kiện đầy, bỏ sự kiện cũ nhất', { dropped })
    }
    await this.persist()
    this.schedule(0)
  }

  schedule(ms) {
    if (this.timer || this.halted) return
    this.timer = this.setTimer(() => {
      this.timer = null
      this.flush().catch((err) => log.error('Lỗi gửi sự kiện', { error: err.message }))
    }, ms)
  }

  stop() {
    if (this.timer) this.clearTimer(this.timer)
    this.timer = null
  }

  // Lấy lô đầu hàng: tối đa BATCH sự kiện và MAX_BATCH_BYTES, xếp theo ts tăng dần.
  takeBatch() {
    const batch = []
    let bytes = 0
    for (const item of this.items) {
      const size = Buffer.byteLength(JSON.stringify(item))
      if (batch.length && (batch.length >= BATCH || bytes + size > MAX_BATCH_BYTES)) break
      batch.push(item)
      bytes += size
    }
    return batch
  }

  // Gửi hết hàng đợi theo lô; trả true khi gửi xong, false khi api chưa nhận (đã hẹn thử lại hoặc dừng).
  // 200: xong cả lô (sự kiện bị api từ chối thì bỏ, không thử lại). 401: sai khóa, dừng.
  // 5xx, 429, mất kết nối: thử lại cả lô. 4xx khác: lô hỏng, bỏ và ghi lỗi.
  async flush() {
    if (this.sending || this.halted) return false
    this.sending = true
    try {
      while (this.items.length) {
        const batch = this.takeBatch()
        const ordered = [...batch].sort((a, b) => String(a.ts).localeCompare(String(b.ts)))
        let status = 0
        let body = null
        try {
          const res = await this.fetch(this.eventsUrl, {
            method: 'POST',
            headers: { 'content-type': 'application/json', authorization: `Bearer ${this.token}` },
            body: JSON.stringify({ events: ordered }),
            signal: AbortSignal.timeout(15_000),
          })
          status = res.status
          if (res.ok && typeof res.json === 'function') body = await res.json().catch(() => null)
        } catch (err) {
          log.warn('Không gửi được sự kiện tới api', { error: err.message, count: batch.length })
        }
        if (status === 401) {
          this.halted = true
          log.error('api báo sai ZALO_BRIDGE_TOKEN, dừng gửi sự kiện tới khi khởi động lại', { pending: this.items.length })
          return false
        }
        if (status === 0 || status === 429 || status >= 500) {
          if (status) log.warn('api chưa nhận lô sự kiện, thử lại sau', { status, count: batch.length })
          this.schedule(this.delay)
          this.delay = Math.min(this.delay * 2, MAX_DELAY_MS)
          return false
        }
        if (status >= 400) {
          log.error('api từ chối cả lô sự kiện, bỏ lô', { status, count: batch.length })
        } else {
          const rejected = body?.data?.rejected
          if (Array.isArray(rejected) && rejected.length) {
            log.warn('api bỏ một số sự kiện', { count: rejected.length, reasons: [...new Set(rejected.map((r) => r.reason))] })
          }
        }
        this.items.splice(0, batch.length)
        this.delay = MIN_DELAY_MS
        await this.persist()
        log.debug('Đã gửi lô sự kiện', { count: batch.length })
      }
      return true
    } finally {
      this.sending = false
    }
  }
}
