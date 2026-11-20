import { describe, expect, it } from 'vitest'
import type { Risk, Stop, StopBooking, TripBrief } from '@/modules/trip/types/trip'
import { bookingLines, canNavigate, defaultDayNo, formatBookingTime, formatDuration, formatKm, groupStops, navigationTarget, pickedDirectionsUrl, pickedInTripOrder, risksByStop, sortTrips, stopCoord, stopSearchText } from '@/modules/trip/utils/trip-utils'

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

describe('chọn điểm để chỉ đường', () => {
  it('điểm trong link: tọa độ 6 chữ số, không có thì tên tìm', () => {
    expect(stopCoord(stop({ lat: 10.1, lng: 106.25 }))).toBe('10.100000,106.250000')
    expect(stopCoord(stop({ lat: null, lng: null, place_query: ' Ao Bà Om, Trà Vinh ' }))).toBe('Ao Bà Om, Trà Vinh')
    expect(stopCoord(stop({ lat: null, lng: null, place_query: null, title: 'Chùa Âng' }))).toBe('Chùa Âng')
  })

  it('không origin, điểm cuối là destination, còn lại là waypoints theo thứ tự lịch trình', () => {
    const a = stop({ id: 1, seq: 1, lat: 10.1, lng: 106.2 })
    const b = stop({ id: 2, seq: 2, lat: null, lng: null, place_query: 'Ao Bà Om, Trà Vinh' })
    const c = stop({ id: 3, seq: 3, lat: 9.9, lng: 106.3 })
    const ordered = pickedInTripOrder([a, b, c], new Set([3, 1, 2]))
    expect(ordered.map((s) => s.id)).toEqual([1, 2, 3])
    const url = pickedDirectionsUrl(ordered)
    expect(url).toBe(
      'https://www.google.com/maps/dir/?api=1&destination=9.900000,106.300000&travelmode=two-wheeler&avoid=highways&waypoints=10.100000,106.200000|Ao%20B%C3%A0%20Om,%20Tr%C3%A0%20Vinh&dir_action=navigate',
    )
    expect(url).not.toContain('origin=')
  })

  it('hai điểm: một waypoint', () => {
    const url = pickedDirectionsUrl([stop({ lat: 1, lng: 2 }), stop({ lat: 3, lng: 4 })])
    expect(url).toContain('destination=3.000000,4.000000')
    expect(url).toContain('waypoints=1.000000,2.000000&')
  })
})

describe('đặt chỗ từ email (QĐ-49)', () => {
  const booking = (extra: Partial<StopBooking>): StopBooking => ({
    booking_id: 71,
    provider: 'Booking.com',
    booking_ref: '4127839501',
    check_in: '2026-11-21T14:00:00+07:00',
    check_out: '2026-11-22T12:00:00+07:00',
    guests: 2,
    price: '1250000.00',
    currency: 'VND',
    cancellation: null,
    status: 'confirmed',
    source: 'email',
    ...extra,
  })

  it('giờ nhận, trả phòng theo giờ Việt Nam; không ghi giờ thì chỉ ngày', () => {
    expect(formatBookingTime('2026-11-21T07:00:00Z')).toBe('14:00 21/11')
    expect(formatBookingTime('2026-11-21T00:00:00+07:00')).toBe('21/11')
    expect(formatBookingTime(null)).toBeNull()
  })

  it('các dòng của khối đặt chỗ', () => {
    expect(bookingLines(booking({}))).toEqual({
      head: 'Đặt qua Booking.com, mã 4127839501',
      times: 'Nhận phòng 14:00 21/11 · Trả phòng 12:00 22/11',
      extra: '2 khách · 1.250.000 đ',
    })
    expect(bookingLines(booking({ provider: null, booking_ref: null, check_out: null, guests: null, price: '120.50', currency: 'USD' }))).toEqual({
      head: 'Đặt chỗ từ email',
      times: 'Nhận phòng 14:00 21/11',
      extra: '120,5 USD',
    })
  })
})

describe('chuỗi tìm có địa phương (lỗi Phước Hải ra Cần Thơ)', () => {
  it('dùng chuỗi đầy đủ của máy chủ', () => {
    expect(stopSearchText(stop({ title: 'Quán Gió', search_query: 'Quán Gió, Phước Hải, Bà Rịa - Vũng Tàu', area: 'Phước Hải, Bà Rịa - Vũng Tàu' }))).toBe('Quán Gió, Phước Hải, Bà Rịa - Vũng Tàu')
  })

  it('không có chuỗi đầy đủ thì ghép tên với địa phương, không lặp khi tên đã có', () => {
    expect(stopSearchText(stop({ title: 'Quán Gió', area: 'Phước Hải, Bà Rịa - Vũng Tàu' }))).toBe('Quán Gió, Phước Hải, Bà Rịa - Vũng Tàu')
    expect(stopSearchText(stop({ title: 'Quán Gió', place_query: 'Quán Gió Phuoc Hai', area: 'Phước Hải' }))).toBe('Quán Gió Phuoc Hai')
    expect(stopSearchText(stop({ title: 'Chùa Âng' }))).toBe('Chùa Âng')
  })

  it('dẫn đường và Chọn điểm: có tọa độ thì dùng tọa độ, không thì chuỗi có địa phương', () => {
    const noCoord = stop({ lat: null, lng: null, title: 'Quán Gió', search_query: 'Quán Gió, Phước Hải, Bà Rịa - Vũng Tàu' })
    expect(navigationTarget(noCoord).query).toBe('Quán Gió, Phước Hải, Bà Rịa - Vũng Tàu')
    expect(stopCoord(noCoord)).toBe('Quán Gió, Phước Hải, Bà Rịa - Vũng Tàu')
    expect(pickedDirectionsUrl([noCoord])).toContain('destination=Qu%C3%A1n%20Gi%C3%B3,%20Ph%C6%B0%E1%BB%9Bc%20H%E1%BA%A3i')
    expect(stopCoord(stop({ lat: 10.42, lng: 107.37, search_query: 'X, Y' }))).toBe('10.420000,107.370000')
  })
})
