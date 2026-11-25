import { describe, expect, it } from 'vitest'
import { findMention, mentionOptions, removeMention } from '@/modules/chat/utils/mentions'

describe('gõ @ để gọi thêm', () => {
  it('chỉ nhận @ đứng đầu hoặc sau khoảng trắng, tới con trỏ', () => {
    expect(findMention('@', 1)).toEqual({ start: 0, query: '' })
    expect(findMention('hỏi @erp', 8)).toEqual({ start: 4, query: 'erp' })
    expect(findMention('mail bao@dego.vn', 16)).toBeNull()
    expect(findMention('@erp xong', 9)).toBeNull()
  })

  it('lọc không dấu, kết nối trước rồi Tìm sâu, Nghĩ kỹ', () => {
    const list = [{ id: 3, name: 'ERP DEGO' }]
    expect(mentionOptions(list, '').map((o) => o.label)).toEqual(['ERP DEGO', 'Tìm sâu', 'Nghĩ kỹ'])
    expect(mentionOptions(list, 'tim').map((o) => o.label)).toEqual(['Tìm sâu'])
    expect(mentionOptions(list, 'erpd').map((o) => o.label)).toEqual(['ERP DEGO'])
  })

  it('chọn xong thì bỏ đoạn @ khỏi chữ', () => {
    expect(removeMention('hỏi @er việc tuần này', { start: 4, query: 'er' })).toEqual({ text: 'hỏi việc tuần này', caret: 4 })
  })
})
