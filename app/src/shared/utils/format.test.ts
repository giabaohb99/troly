import { describe, expect, it } from 'vitest'
import { formatDayTitle, formatModelLabel, formatMoney, formatMoneyShort, formatTime, formatUsd, formatWhen, parseMoney, toDateKey } from '@/shared/utils/format'

describe('parseMoney', () => {
  it.each([
    ['45k', 45_000],
    ['45K', 45_000],
    ['45.000', 45_000],
    ['45,000', 45_000],
    ['45000đ', 45_000],
    ['1,2tr', 1_200_000],
    ['1.5 triệu', 1_500_000],
    ['1tr2', 1_200_000],
    ['2tr05', 2_050_000],
    ['3 ty', 3_000_000_000],
    ['120 nghìn', 120_000],
  ])('đọc %s', (input, expected) => {
    expect(parseMoney(input)).toBe(expected)
  })

  it.each(['', 'abc', '0', '-5k', '45kk'])('từ chối %s', (input) => {
    expect(parseMoney(input)).toBeNull()
  })
})

describe('định dạng tiền', () => {
  it('đủ', () => {
    expect(formatMoney(45_000)).toBe('45.000 đ')
  })
  it('tóm tắt', () => {
    expect(formatMoneyShort(45_000)).toBe('45k')
    expect(formatMoneyShort(1_200_000)).toBe('1,2 tr')
    expect(formatMoneyShort(800)).toBe('800')
  })
})

describe('ngày giờ theo giờ Việt Nam', () => {
  it('giờ và khóa ngày đổi múi giờ', () => {
    expect(formatTime('2026-11-18T17:30:00Z')).toBe('00:30')
    expect(toDateKey('2026-11-18T17:30:00Z')).toBe('2026-11-19')
  })
  it('tiêu đề ngày', () => {
    expect(formatDayTitle('2026-11-18')).toBe('Thứ Tư, 18/11')
  })
})

describe('formatModelLabel', () => {
  it('rút gọn tên model', () => {
    expect(formatModelLabel('claude-haiku-5-5')).toBe('Haiku 5.5')
    expect(formatModelLabel('claude-sonnet-5-5-20261101')).toBe('Sonnet 5.5')
    expect(formatModelLabel(null)).toBeNull()
  })
})

describe('formatWhen', () => {
  it('hôm nay ra giờ, ngày khác ra ngày tháng', () => {
    expect(formatWhen('2026-11-18T02:05:00Z', '2026-11-18')).toBe('09:05')
    expect(formatWhen('2026-11-16T02:05:00Z', '2026-11-18')).toBe('16/11')
  })
})

describe('formatUsd', () => {
  it('dưới 1 USD hiện 4 chữ số lẻ để thấy được chi phí từng câu', () => {
    expect(formatUsd(0.0012)).toBe('0,0012 USD')
    expect(formatUsd(0.00042)).toBe('0,0004 USD')
    expect(formatUsd(0)).toBe('0,00 USD')
  })

  it('từ 1 USD hiện 2 chữ số lẻ', () => {
    expect(formatUsd(1.384)).toBe('1,38 USD')
    expect(formatUsd(200)).toBe('200,00 USD')
  })
})
