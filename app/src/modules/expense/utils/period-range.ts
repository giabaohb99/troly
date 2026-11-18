import type { Period } from '@/modules/expense/types/expense'

// Khoảng thời gian của kỳ theo giờ Việt Nam (UTC+7, không đổi giờ mùa hè). `to` không tính (12 mục 3.4).
const OFFSET_MS = 7 * 3_600_000

function vnMidnightUtc(year: number, month: number, day: number): number {
  return Date.UTC(year, month, day) - OFFSET_MS
}

function toVnIso(ms: number): string {
  const d = new Date(ms + OFFSET_MS)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:00+07:00`
}

export function periodRange(period: Period, now = new Date()): { from: string; to: string } {
  const vn = new Date(now.getTime() + OFFSET_MS)
  const y = vn.getUTCFullYear()
  const m = vn.getUTCMonth()
  const d = vn.getUTCDate()
  if (period === 'day') return { from: toVnIso(vnMidnightUtc(y, m, d)), to: toVnIso(vnMidnightUtc(y, m, d + 1)) }
  if (period === 'week') {
    const mondayOffset = (vn.getUTCDay() + 6) % 7
    return { from: toVnIso(vnMidnightUtc(y, m, d - mondayOffset)), to: toVnIso(vnMidnightUtc(y, m, d - mondayOffset + 7)) }
  }
  return { from: toVnIso(vnMidnightUtc(y, m, 1)), to: toVnIso(vnMidnightUtc(y, m + 1, 1)) }
}

// Giá trị cho ô datetime-local (giờ Việt Nam) và ngược lại.
export function toLocalInput(iso: string): string {
  return toVnIso(Date.parse(iso)).slice(0, 16)
}

export function fromLocalInput(value: string): string {
  return `${value}:00+07:00`
}
