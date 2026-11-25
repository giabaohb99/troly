import { describe, expect, it } from 'vitest'
import { findMention, mentionOptions, removeMention } from '@/modules/chat/utils/mentions'

describe('gõ @ để gọi đoạn chat khác', () => {
  it('chỉ nhận @ đứng đầu hoặc sau khoảng trắng, tới con trỏ', () => {
    expect(findMention('@', 1)).toEqual({ start: 0, query: '' })
    expect(findMention('hỏi @cong', 9)).toEqual({ start: 4, query: 'cong' })
    expect(findMention('mail bao@dego.vn', 16)).toBeNull()
    expect(findMention('@cong xong', 10)).toBeNull()
  })

  it('lọc không dấu, bỏ khoảng trắng theo tên đoạn chat', () => {
    const list = [
      { id: 1, label: 'Công việc DEGO', hint: '' },
      { id: 2, label: 'Chi tiêu', hint: '' },
    ]
    expect(mentionOptions(list, '').map((o) => o.id)).toEqual([1, 2])
    expect(mentionOptions(list, 'congviec').map((o) => o.id)).toEqual([1])
    expect(mentionOptions(list, 'tiêu').map((o) => o.id)).toEqual([2])
  })

  it('chọn xong thì bỏ đoạn @ khỏi chữ', () => {
    expect(removeMention('hỏi @co việc tuần này', { start: 4, query: 'co' })).toEqual({ text: 'hỏi việc tuần này', caret: 4 })
  })
})
