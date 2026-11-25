import { describe, expect, it } from 'vitest'
import { splitTables } from '@/shared/utils/text-tables'

describe('bảng trong tin nhắn', () => {
  it('tách bảng Markdown khỏi chữ, giữ chữ trước và sau', () => {
    const text = 'Lãi suất 12 tháng:\n\n| Ngân hàng | Lãi (%/năm) |\n|---|---:|\n| Agribank | 6,8 |\n| Techcombank | 6,25 |\n\nNên kiểm lại tại quầy.'
    expect(splitTables(text)).toEqual([
      { type: 'text', value: 'Lãi suất 12 tháng:' },
      { type: 'table', header: ['Ngân hàng', 'Lãi (%/năm)'], rows: [['Agribank', '6,8'], ['Techcombank', '6,25']] },
      { type: 'text', value: 'Nên kiểm lại tại quầy.' },
    ])
  })

  it('dòng có gạch đứng mà không có dòng kẻ thì vẫn là chữ; dòng thiếu ô được bù ô trống', () => {
    expect(splitTables('a | b | c')).toEqual([{ type: 'text', value: 'a | b | c' }])
    expect(splitTables('| A | B |\n|--|--|\n| 1 |')).toEqual([{ type: 'table', header: ['A', 'B'], rows: [['1', '']] }])
  })
})
