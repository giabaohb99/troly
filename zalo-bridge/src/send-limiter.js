// Gửi tin lần lượt, tối đa N tin mỗi phút, giãn ngẫu nhiên giữa hai tin, hàng chờ ngắn (QĐ-52: giảm rủi ro khóa).

export class RateLimitError extends Error {
  constructor(retryAfter = 60) {
    super('Gửi quá nhanh, thử lại sau ít phút.')
    this.code = 'RATE_LIMITED'
    this.retryAfter = retryAfter
  }
}

export class SendLimiter {
  constructor({
    perMinute = 20, queueMax = 5, minGapMs = 2_000, maxGapMs = 5_000,
    now = Date.now, sleep = (ms) => new Promise((r) => setTimeout(r, ms)), random = Math.random,
  } = {}) {
    Object.assign(this, { perMinute, queueMax, minGapMs, maxGapMs, now, sleep, random })
    this.sentAt = []
    this.pending = 0
    this.chain = Promise.resolve()
    this.lastSentAt = 0
  }

  // Chạy task theo thứ tự; quá hàng chờ thì báo RATE_LIMITED ngay, không chờ.
  run(task) {
    if (this.pending >= this.queueMax) return Promise.reject(new RateLimitError(this.retryAfterSeconds()))
    this.pending += 1
    const job = this.chain.then(async () => {
      try {
        await this.waitTurn()
        const result = await task()
        const t = this.now()
        this.sentAt.push(t)
        this.lastSentAt = t
        return result
      } finally {
        this.pending -= 1
      }
    })
    this.chain = job.catch(() => {})
    return job
  }

  // Ước số giây nên chờ trước khi gửi lại: hết cửa sổ một phút hoặc hết hàng chờ hiện có.
  retryAfterSeconds() {
    const t = this.now()
    const recent = this.sentAt.filter((s) => t - s < 60_000)
    const windowWait = recent.length >= this.perMinute ? recent[0] + 60_000 - t : 0
    const queueWait = this.pending * this.maxGapMs
    return Math.max(1, Math.ceil(Math.max(windowWait, queueWait) / 1000))
  }

  async waitTurn() {
    for (;;) {
      const t = this.now()
      this.sentAt = this.sentAt.filter((s) => t - s < 60_000)
      const gap = this.minGapMs + Math.floor(this.random() * (this.maxGapMs - this.minGapMs))
      const waitGap = this.lastSentAt ? this.lastSentAt + gap - t : 0
      const waitWindow = this.sentAt.length >= this.perMinute ? this.sentAt[0] + 60_000 - t : 0
      const wait = Math.max(waitGap, waitWindow, 0)
      if (wait <= 0) return
      await this.sleep(wait)
    }
  }
}
