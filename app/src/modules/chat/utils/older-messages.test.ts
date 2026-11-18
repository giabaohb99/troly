import { describe, expect, it } from 'vitest'
import type { ChatMessage } from '@/modules/chat/types/chat'
import { hasGap, mergeOlder } from '@/modules/chat/utils/older-messages'

const msg = (id: number): ChatMessage => ({ id, role: 'user', text: `tin ${id}`, model: null, citations: null, attachments: null, actions: null, status: 'done', created_at: '2026-11-18T08:00:00Z' })

describe('tin cũ', () => {
  it('tin cũ đứng trước, bỏ trùng với trang mới nhất', () => {
    const merged = mergeOlder([msg(1), msg(2), msg(3)], [msg(3), msg(4)])
    expect(merged.map((m) => m.id)).toEqual([1, 2, 3, 4])
  })

  it('chưa tải tin cũ thì giữ nguyên trang mới nhất', () => {
    const latest = [msg(5), msg(6)]
    expect(mergeOlder([], latest)).toBe(latest)
  })

  it('trang mới nhất trượt quá con trỏ ban đầu thì có khoảng hở', () => {
    expect(hasGap('100', '100')).toBe(false)
    expect(hasGap('100', '140')).toBe(true)
    expect(hasGap(null, '140')).toBe(false)
    expect(hasGap('100', null)).toBe(false)
  })
})
