import { describe, expect, it } from 'vitest'
import { SPEAK_MORE, toSpeakable } from '@/shared/voice/speakable'

describe('chữ để đọc to', () => {
  it('bỏ định dạng, link, khối mã', () => {
    const text = '## Lịch chiều nay\n\n- **14:00** họp với *anh Minh*\n- Xem [bản đồ](https://maps.app/x) tại https://maps.app/y\n\n```\nmã\n```'
    expect(toSpeakable(text)).toBe('Lịch chiều nay. 14:00 họp với anh Minh. Xem bản đồ tại.')
  })

  it('bảng thành câu, không đọc dấu gạch', () => {
    const text = '| Món | Giá |\n|---|---|\n| Cơm | 45k |'
    const out = toSpeakable(text)
    expect(out).not.toContain('|')
    expect(out).not.toContain('---')
    expect(out).toContain('Cơm')
  })

  it('dài quá thì cắt ở cuối câu rồi nói phần còn lại trên màn hình', () => {
    const sentence = 'Đây là một câu khá dài để thử cắt chữ khi đọc to trả lời. '
    const out = toSpeakable(sentence.repeat(20))
    expect(out.endsWith(SPEAK_MORE)).toBe(true)
    expect(out.length).toBeLessThanOrEqual(600 + SPEAK_MORE.length + 1)
    expect(out.replace(SPEAK_MORE, '').trim().endsWith('.')).toBe(true)
  })

  it('ngắn thì đọc nguyên', () => {
    expect(toSpeakable('Đã ghi 45k cơm trưa.')).toBe('Đã ghi 45k cơm trưa.')
  })
})
