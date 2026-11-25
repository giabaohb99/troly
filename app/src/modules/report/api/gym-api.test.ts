import { describe, expect, it } from 'vitest'
import { gymDayText, gymLines, type GymReport } from '@/modules/report/api/gym-api'

const report = (extra: Partial<GymReport> = {}): GymReport => ({
  period: 'week',
  from: '2026-11-23',
  to: '2026-11-29',
  sessions_done: 2,
  sessions_planned: 4,
  lift_highlights: [
    { exercise: 'Đẩy ngực', from_kg: 60, to_kg: 62.5, delta_kg: 2.5 },
    { exercise: 'Kéo xà', from_kg: null, to_kg: 10, delta_kg: 10 },
  ],
  weight: { first_kg: 72.4, last_kg: 71.8, first_date: '2026-11-23', last_date: '2026-11-25' },
  protein: { avg_g: 118.4, target_g: 140, days_logged: 3 },
  today: { title: 'Kéo', done: false },
  tomorrow: null,
  ...extra,
})

describe('thẻ Tập luyện (QĐ-54)', () => {
  it('buổi, tạ, cân nặng, đạm', () => {
    const l = gymLines(report())
    expect(l.sessions).toBe('2/4')
    expect(l.behind).toBe(true)
    expect(l.lifts).toEqual(['Đẩy ngực: 60 kg → 62,5 kg (+2,5)', 'Kéo xà: 10 kg (+10)'])
    expect(l.weight).toBe('72,4 kg → 71,8 kg (-0,6)')
    expect(l.protein).toBe('118 g/ngày, mục tiêu 140 g (84%)')
    expect(l.proteinLow).toBe(true)
  })

  it('thiếu số liệu thì bỏ dòng; đủ buổi không cảnh báo', () => {
    const l = gymLines(report({ sessions_done: 4, weight: { first_kg: null, last_kg: 70, first_date: null, last_date: null }, protein: { avg_g: null, target_g: 140, days_logged: 0 }, lift_highlights: [] }))
    expect(l.behind).toBe(false)
    expect(l.weight).toBe('70 kg')
    expect(l.protein).toBeNull()
    expect(l.lifts).toEqual([])
  })

  it('số buổi đủ hiệp và dòng ngày tập', () => {
    expect(gymLines(report({ sessions_done: 3, sessions_complete: 2 })).complete).toBe('2 buổi đủ hiệp')
    expect(gymLines(report({ sessions_done: 3, sessions_complete: 3 })).complete).toBeNull()
    expect(gymDayText({ title: 'Kéo', exercises: ['a', 'b', 'c', 'd'], done: true })).toBe('Kéo (4 bài), đã tập')
    expect(gymDayText({ title: 'Ngày nghỉ', rest: true })).toBe('Nghỉ')
    expect(gymDayText(null)).toBe('Nghỉ')
  })
})
