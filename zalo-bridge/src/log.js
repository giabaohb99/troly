// Nhật ký JSON một dòng. Không bao giờ ghi nội dung tin, cookie, khóa (60 mục 3.9).
import { createHash } from 'node:crypto'

const LEVELS = { DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40 }
let threshold = LEVELS.INFO

export function setLogLevel(level) {
  threshold = LEVELS[String(level).toUpperCase()] ?? LEVELS.INFO
}

// Băm mã hội thoại, mã người để truy vết mà không lộ danh tính trong nhật ký.
export function hashId(id) {
  return id ? createHash('sha256').update(String(id)).digest('hex').slice(0, 10) : null
}

function write(level, msg, extra) {
  if (LEVELS[level] < threshold) return
  const line = { ts: new Date().toISOString(), level, msg, ...extra }
  process.stdout.write(JSON.stringify(line) + '\n')
}

export const log = {
  debug: (msg, extra) => write('DEBUG', msg, extra),
  info: (msg, extra) => write('INFO', msg, extra),
  warn: (msg, extra) => write('WARNING', msg, extra),
  error: (msg, extra) => write('ERROR', msg, extra),
}
