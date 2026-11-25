import { describe, expect, it } from 'vitest'
import { ApiError } from '@/core/api/api-error'
import type { InboxMessage } from '@/modules/inbox/types/inbox'
import { groupByDay, isZaloFullKey, reconcilePending, zaloSendErrorText, type PendingSend } from '@/modules/inbox/utils/zalo'
import { zaloStateText } from '@/shared/api/zalo-api'

const msg = (id: number, at: string, extra: Partial<InboxMessage> = {}): InboxMessage => ({
  id,
  source: 'zalo_bridge',
  app: 'zalo',
  sender: 'Chị Lan',
  conversation_key: 'zalo:u:123',
  conversation_title: 'Chị Lan',
  is_group: false,
  subject: null,
  text: 'chào em',
  hidden_content: false,
  posted_at: at,
  status: 'seen',
  importance: 'normal',
  importance_reason: null,
  ...extra,
})

const pending = (extra: Partial<PendingSend>): PendingSend => ({ clientRef: 'r1', text: 'ok chị', fileNames: [], createdAt: Date.parse('2026-11-25T03:00:00Z'), status: 'sent', ...extra })

describe('Zalo (QĐ-52)', () => {
  it('khóa Zalo đầy đủ của bridge', () => {
    expect(isZaloFullKey('zalo:u:84901')).toBe(true)
    expect(isZaloFullKey('zalo:g:5521')).toBe(true)
    expect(isZaloFullKey('zalo:lan')).toBe(false)
    expect(isZaloFullKey('sms:0909')).toBe(false)
  })

  it('gom tin theo ngày giờ Việt Nam, cũ trước', () => {
    const groups = groupByDay([msg(3, '2026-11-25T02:00:00Z'), msg(1, '2026-11-24T17:30:00Z'), msg(2, '2026-11-24T10:00:00Z')])
    expect(groups.map((g) => [g.day, g.items.map((m) => m.id)])).toEqual([
      ['2026-11-24', [2]],
      ['2026-11-25', [1, 3]],
    ])
  })

  it('bỏ tin tạm khi bridge báo lại tin của mình; giữ tin lỗi, tin chưa thấy', () => {
    const server = [msg(10, '2026-11-25T03:00:03Z', { is_self: true, text: 'ok chị' }), msg(11, '2026-11-25T03:00:05Z', { is_self: false, text: 'ok chị' })]
    expect(reconcilePending([pending({})], server)).toEqual([])
    expect(reconcilePending([pending({ status: 'failed' })], server)).toHaveLength(1)
    expect(reconcilePending([pending({ text: 'khác' })], server)).toHaveLength(1)
    // Chỉ gửi tệp: khớp tin của mình có đủ tệp.
    const withFile = [msg(12, '2026-11-25T03:00:04Z', { is_self: true, text: null, media: [{ type: 'image', name: 'a.jpg', size: 1, mime: 'image/jpeg', status: 'done', file_id: 9 }] })]
    expect(reconcilePending([pending({ text: '', fileNames: ['a.jpg'] })], withFile)).toEqual([])
  })

  it('câu lỗi gửi và trạng thái đăng nhập', () => {
    const limited = new ApiError(429, 'x', 'RATE_LIMITED')
    limited.retryAfter = 12.4
    expect(zaloSendErrorText(limited)).toBe('Gửi chậm lại, thử lại sau 13 giây.')
    expect(zaloSendErrorText(new ApiError(409, 'x', 'NOT_LOGGED_IN'))).toBe('Zalo chưa đăng nhập. Vào Cài đặt → Zalo để quét mã QR.')
    expect(zaloStateText({ state: 'logged_in', account: { uid: '1', name: 'Gia Bảo' } })).toBe('Đã đăng nhập Gia Bảo')
    expect(zaloStateText({ state: 'kicked', account: null })).toContain('10 phút')
    expect(zaloStateText({ state: 'unavailable', account: null, message: 'Dịch vụ Zalo tắt' })).toBe('Dịch vụ Zalo tắt')
  })
})
