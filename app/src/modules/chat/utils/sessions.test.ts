import { describe, expect, it } from 'vitest'
import type { ChatSession } from '@/modules/chat/types/chat'
import { matchSession, openSessionPath, rememberOpenSession, sessionTitle, sortSessions } from '@/modules/chat/utils/sessions'

const s = (id: number, extra: Partial<ChatSession> = {}): ChatSession => ({ id, title: null, pinned: false, last_message_at: null, last_preview: null, created_at: null, ...extra })

describe('phiên chat (QĐ-51)', () => {
  it('tên hiện: tên đặt, không thì theo lúc tạo, phiên cũ theo ngày', () => {
    expect(sessionTitle(s(1, { title: ' Lịch trình Bến Tre ' }))).toBe('Lịch trình Bến Tre')
    expect(sessionTitle(s(2, { created_at: '2026-11-25T01:30:00Z' }))).toBe('Phiên 25/11 08:30')
    expect(sessionTitle(s(3, { local_date: '2026-11-20' }))).toBe('Phiên 20/11')
    expect(sessionTitle(s(4))).toBe('Phiên mới')
    expect(sessionTitle(null)).toBe('Trợ lý')
  })

  it('ghim trước, rồi theo lần nhắn cuối', () => {
    const items = [
      s(1, { last_message_at: '2026-11-25T08:00:00Z' }),
      s(2, { pinned: true, last_message_at: '2026-11-19T08:00:00Z' }),
      s(3, { last_message_at: '2026-11-24T08:00:00Z' }),
      s(4, { created_at: '2026-11-25T09:00:00Z' }),
    ]
    expect(sortSessions(items).map((x) => x.id)).toEqual([2, 4, 1, 3])
  })

  it('tìm theo tên và đoạn tin cuối, không phân biệt dấu', () => {
    const session = s(1, { title: 'Lịch trình Bến Tre', last_preview: 'Em đã lập chuyến, ghé Cồn Phụng' })
    expect(matchSession(session, 'ben tre')).toBe(true)
    expect(matchSession(session, 'con phung')).toBe(true)
    expect(matchSession(session, 'đà lạt')).toBe(false)
    expect(matchSession(session, '  ')).toBe(true)
  })

  it('chia sẻ từ app khác vào phiên đang mở', () => {
    rememberOpenSession(7)
    expect(openSessionPath()).toBe('/?phien=7')
  })
})
