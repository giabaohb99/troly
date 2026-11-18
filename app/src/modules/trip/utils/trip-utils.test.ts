import { describe, expect, it } from 'vitest'
import type { Risk, Stop, TripBrief } from '@/modules/trip/types/trip'
import { canNavigate, defaultDayNo, formatDuration, formatKm, groupStops, navigationTarget, risksByStop, sortTrips } from '@/modules/trip/utils/trip-utils'

const brief = (id: number, start: string | null, end: string | null): TripBrief => ({
  id, title: `Chuyến ${id}`, start_date: start, end_date: end, nights: null, travel_mode: 'motorbike', status: 'planned', total_km: null, red_count: 0, yellow_count: 0, needs_confirmation_count: 0,
})

const stop = (extra: Partial<Stop>): Stop => ({
  id: 1, day_no: 1, seq: 1, title: 'Điểm', category: 'tham_quan', role: 'main', parent_stop_id: null, source_url: null, time_text: null, planned_start: null, planned_end: null, approx: false, fixed: false, optional: false,
  stay_minutes: null, place_query: null, place_id: null, lat: 10.1, lng: 106.2, resolve_status: 'ok', phone: null, cost_note: null, note: null, leg_km: null, leg_minutes: null, ...extra,
})

const risk = (stopId: number | null, level: Risk['level'], code = 'R1'): Risk => ({ code, level, day_no: 1, stop_id: stopId, message: code, suggestion: null, checked_at: null })

describe('định dạng chuyến', () => {
  it('giờ chạy', () => {
    expect(formatDuration(130)).toBe('2 giờ 10')
    expect(formatDuration(120)).toBe('2 giờ')
    expect(formatDuration(45)).toBe('45 phút')
    expect(formatDuration(null)).toBe(null)
  })

  it('quãng đường', () => {
    expect(formatKm(85.4)).toBe('85 km')
    expect(formatKm(1.5)).toBe('1,5 km')
    expect(formatKm(null)).toBe(null)
  })
})

describe('rủi ro và dẫn đường', () => {
  it('gom rủi ro theo điểm, đỏ trước', () => {
    const map = risksByStop([risk(5, 'yellow', 'R4'), risk(5, 'red', 'R3'), risk(null, 'red', 'R6')])
    expect(map.get(5)?.map((r) => r.code)).toEqual(['R3', 'R4'])
    expect(map.size).toBe(1)
  })

  it('điểm chính hoặc đi qua có Dẫn đường, kể cả khi chưa có tọa độ', () => {
    expect(canNavigate(stop({}))).toBe(true)
    expect(canNavigate(stop({ lat: null, lng: null, resolve_status: 'manual' }))).toBe(true)
    expect(canNavigate(stop({ role: 'alternative' }))).toBe(false)
    expect(canNavigate(stop({ role: 'via' }))).toBe(true)
  })

  it('không có tọa độ thì dẫn đường theo tên tìm, rồi theo tên điểm', () => {
    expect(navigationTarget(stop({}))).toEqual({ lat: 10.1, lng: 106.2, query: null })
    expect(navigationTarget(stop({ lat: null, lng: null, place_query: 'Ao Bà Om, Trà Vinh' }))).toEqual({ lat: null, lng: null, query: 'Ao Bà Om, Trà Vinh' })
    expect(navigationTarget(stop({ lat: null, lng: null, title: 'Chùa Âng' })).query).toBe('Chùa Âng')
  })
})

describe('gom điểm phụ', () => {
  it('điểm phụ đứng ngay dưới điểm chính; điểm chính bị mất thì điểm phụ đứng như điểm thường', () => {
    const list = groupStops([
      stop({ id: 1, seq: 1 }),
      stop({ id: 2, seq: 2 }),
      stop({ id: 3, seq: 3, role: 'alternative', parent_stop_id: 1 }),
      stop({ id: 4, seq: 4, role: 'backup', parent_stop_id: 99 }),
    ])
    expect(list.map((s) => s.id)).toEqual([1, 3, 2, 4])
  })
})

describe('thứ tự chuyến', () => {
  it('đang đi, sắp tới gần trước, đã qua mới trước, chưa có ngày cuối', () => {
    const sorted = sortTrips(
      [brief(1, '2026-10-01', '2026-10-03'), brief(2, '2026-12-20', '2026-12-22'), brief(3, '2026-11-17', '2026-11-19'), brief(4, '2026-11-25', '2026-11-26'), brief(5, null, null), brief(6, '2026-11-01', '2026-11-02')],
      '2026-11-18',
    )
    expect(sorted.map((t) => t.id)).toEqual([3, 4, 2, 5, 6, 1])
  })

  it('ngày mở mặc định', () => {
    const days = [{ day_no: 1, date: '2026-11-17' }, { day_no: 2, date: '2026-11-18' }]
    expect(defaultDayNo(days, '2026-11-18')).toBe(2)
    expect(defaultDayNo(days, '2026-12-01')).toBe(1)
  })
})
