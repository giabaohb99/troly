import { ApiError, getErrorMessage } from '@/core/api/api-error'
import type { InboxMessage } from '@/modules/inbox/types/inbox'
import { toDateKey } from '@/shared/utils/format'

// Khung chat Zalo (QĐ-52): luật thuần, kiểm bằng Vitest.

// Khóa hội thoại Zalo đầy đủ của bridge: zalo:u:<thread_id> (một-một), zalo:g:<thread_id> (nhóm). Khóa cũ đọc từ
// thông báo (zalo:<tên>) vẫn mở màn hộp tin cũ.
export const isZaloFullKey = (key: string) => /^zalo:[ug]:./.test(key)
export const isZaloGroupKey = (key: string) => key.startsWith('zalo:g:')

export function sortOldestFirst(items: InboxMessage[]): InboxMessage[] {
  return [...items].sort((a, b) => Date.parse(a.posted_at) - Date.parse(b.posted_at) || a.id - b.id)
}

// Gom tin theo ngày (giờ Việt Nam), cũ trước.
export function groupByDay(items: InboxMessage[]): { day: string; items: InboxMessage[] }[] {
  const groups: { day: string; items: InboxMessage[] }[] = []
  for (const m of sortOldestFirst(items)) {
    const day = toDateKey(m.posted_at)
    const last = groups[groups.length - 1]
    if (last?.day === day) last.items.push(m)
    else groups.push({ day, items: [m] })
  }
  return groups
}

// Tin mình vừa gửi, hiện tạm tới khi bridge báo lại (vài giây).
export interface PendingSend {
  clientRef: string
  text: string
  fileNames: string[]
  createdAt: number
  status: 'sending' | 'sent' | 'failed'
  error?: string
}

// Bỏ tin tạm đã có bản thật: tin của mình cùng chữ (hoặc cùng số tệp khi chỉ gửi tệp), gửi sau lúc bấm gửi (trừ 10 giây
// lệch giờ). Tin lỗi giữ lại để người dùng thấy và gửi lại.
export function reconcilePending(pending: PendingSend[], server: InboxMessage[]): PendingSend[] {
  const used = new Set<number>()
  return pending.filter((p) => {
    if (p.status !== 'sent') return true
    const match = server.find(
      (m) =>
        !used.has(m.id) &&
        m.is_self &&
        Date.parse(m.posted_at) >= p.createdAt - 10_000 &&
        (p.text ? (m.text ?? '').trim() === p.text.trim() : (m.media?.length ?? 0) >= p.fileNames.length),
    )
    if (match) used.add(match.id)
    return !match
  })
}

// Câu lỗi gửi tin Zalo theo mã máy chủ.
export function zaloSendErrorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'NOT_LOGGED_IN') return 'Zalo chưa đăng nhập. Vào Cài đặt → Zalo để quét mã QR.'
    if (error.code === 'RATE_LIMITED' || error.status === 429)
      return error.retryAfter ? `Gửi chậm lại, thử lại sau ${Math.ceil(error.retryAfter)} giây.` : 'Gửi chậm lại, Zalo giới hạn 20 tin mỗi phút.'
    if (error.code === 'THREAD_NOT_FOUND') return 'Không tìm thấy hội thoại này trên Zalo.'
    if (error.code === 'ZALO_BRIDGE_UNAVAILABLE' || error.status === 503) return 'Dịch vụ Zalo đang tắt, thử lại sau.'
  }
  return getErrorMessage(error)
}

export const needsZaloLogin = (error: unknown) => error instanceof ApiError && error.code === 'NOT_LOGGED_IN'
