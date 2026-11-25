import { apiGet, toQuery } from '@/core/api/http-client'
import type { Card } from '@/modules/report/api/report-api'

// Thẻ Tập luyện (QĐ-54): dữ liệu app gym qua máy chủ Trợ lý, dạng đã chốt với agent kiến trúc (25/11).
// week là 7 ngày tới hôm nay, month là 30 ngày tới hôm nay (không phải tuần, tháng lịch).

export type GymPeriod = 'week' | 'month'

export interface GymReport {
  period: GymPeriod
  from: string
  to: string
  // Số ngày có tập; buổi đủ hiệp; số buổi theo lịch.
  sessions_done: number
  sessions_complete?: number
  sessions_planned: number
  // Bài tăng tạ nổi bật trong khoảng (tối đa 3).
  lift_highlights: { exercise: string; from_kg: number | null; to_kg: number; delta_kg: number }[]
  weight: { first_kg: number | null; last_kg: number | null; first_date: string | null; last_date: string | null } | null
  protein: { avg_g: number | null; target_g: number | null; days_logged: number } | null
  today: GymDay | null
  tomorrow: GymDay | null
  app_url?: string | null
}

// Buổi theo lịch của một ngày; ngày nghỉ thì rest = true, title là *Ngày nghỉ*.
export interface GymDay {
  date?: string
  title: string
  rest?: boolean
  exercises?: string[]
  done?: boolean
}

export const GYM_APP_URL = 'https://gym.baohuynh.io.vn'

// Một dòng mô tả ngày tập: *Kéo (4 bài), đã tập*; ngày nghỉ hoặc không có lịch là *Nghỉ*.
export function gymDayText(day: GymDay | null): string {
  if (!day || day.rest) return 'Nghỉ'
  const count = day.exercises?.length ? ` (${day.exercises.length} bài)` : ''
  return `${day.title}${count}${day.done ? ', đã tập' : ''}`
}

export const getGymReport = (period: GymPeriod) => apiGet<Card<GymReport>>(`/reports/gym${toQuery({ period })}`)

const kg = (n: number) => `${n.toLocaleString('vi-VN', { maximumFractionDigits: 1 })} kg`

// Các dòng chữ của thẻ (kiểm bằng Vitest).
export function gymLines(r: GymReport) {
  const sessions = `${r.sessions_done}/${r.sessions_planned}`
  // Có ngày tập chưa đủ hiệp thì ghi thêm số buổi đủ.
  const complete = r.sessions_complete != null && r.sessions_complete < r.sessions_done ? `${r.sessions_complete} buổi đủ hiệp` : null
  const behind = r.sessions_planned > 0 && r.sessions_done < r.sessions_planned
  let weight: string | null = null
  if (r.weight?.first_kg != null && r.weight.last_kg != null) {
    const diff = Math.round((r.weight.last_kg - r.weight.first_kg) * 10) / 10
    const sign = diff > 0 ? '+' : diff < 0 ? '-' : '±'
    weight = `${kg(r.weight.first_kg)} → ${kg(r.weight.last_kg)} (${sign}${Math.abs(diff).toLocaleString('vi-VN')})`
  } else if (r.weight?.last_kg != null) {
    weight = kg(r.weight.last_kg)
  }
  let protein: string | null = null
  let proteinLow = false
  if (r.protein?.avg_g != null) {
    const avg = Math.round(r.protein.avg_g)
    if (r.protein.target_g) {
      const pct = Math.round((avg / r.protein.target_g) * 100)
      protein = `${avg} g/ngày, mục tiêu ${Math.round(r.protein.target_g)} g (${pct}%)`
      proteinLow = pct < 90
    } else protein = `${avg} g/ngày`
  }
  const lifts = r.lift_highlights.slice(0, 3).map((l) => `${l.exercise}: ${l.from_kg != null ? `${kg(l.from_kg)} → ` : ''}${kg(l.to_kg)} (+${l.delta_kg.toLocaleString('vi-VN', { maximumFractionDigits: 1 })})`)
  return { sessions, complete, behind, weight, protein, proteinLow, lifts }
}
