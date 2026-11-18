import { describe, expect, it } from 'vitest'
import { fromLocalInput, periodRange, toLocalInput } from '@/modules/expense/utils/period-range'

// 2026-11-18 là thứ Tư. 17:30 UTC là 00:30 ngày 19/11 giờ Việt Nam.
const late = new Date('2026-11-18T17:30:00Z')

describe('periodRange', () => {
  it('ngày theo giờ Việt Nam', () => {
    expect(periodRange('day', late)).toEqual({ from: '2026-11-19T00:00:00+07:00', to: '2026-11-20T00:00:00+07:00' })
  })
  it('tuần bắt đầu thứ Hai', () => {
    expect(periodRange('week', new Date('2026-11-18T03:00:00Z'))).toEqual({ from: '2026-11-16T00:00:00+07:00', to: '2026-11-23T00:00:00+07:00' })
  })
  it('chủ nhật thuộc tuần trước', () => {
    expect(periodRange('week', new Date('2026-11-22T10:00:00Z')).from).toBe('2026-11-16T00:00:00+07:00')
  })
  it('tháng, qua năm', () => {
    expect(periodRange('month', new Date('2026-12-31T18:00:00Z'))).toEqual({ from: '2027-01-01T00:00:00+07:00', to: '2027-02-01T00:00:00+07:00' })
  })
})

describe('ô ngày giờ', () => {
  it('đổi qua lại giữ giờ Việt Nam', () => {
    expect(toLocalInput('2026-11-18T05:10:00Z')).toBe('2026-11-18T12:10')
    expect(fromLocalInput('2026-11-18T12:10')).toBe('2026-11-18T12:10:00+07:00')
  })
})
