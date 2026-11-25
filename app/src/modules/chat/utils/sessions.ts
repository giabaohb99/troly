import type { ChatSession } from '@/modules/chat/types/chat'
import { formatTime, toDateKey } from '@/shared/utils/format'

// Tên hiện của phiên: tên đã đặt, không thì *Phiên 25/11 08:30* theo lúc tạo (hoặc ngày của phiên cũ theo ngày).
export function sessionTitle(s: ChatSession | null | undefined): string {
  if (!s) return 'Trợ lý'
  const title = s.title?.trim()
  if (title) return title
  const at = s.started_at ?? s.created_at ?? s.last_message_at
  if (at && !Number.isNaN(Date.parse(at))) {
    const [, m, d] = toDateKey(at).split('-')
    return `Phiên ${d}/${m} ${formatTime(at)}`
  }
  if (s.local_date) {
    const [, m, d] = s.local_date.split('-')
    return `Phiên ${d}/${m}`
  }
  return 'Phiên mới'
}

const lastAt = (s: ChatSession) => Date.parse(s.last_message_at ?? s.started_at ?? s.created_at ?? s.local_date ?? '') || 0

// Phiên nhận chia sẻ mặc định (QĐ-51 bước 2): phiên hoạt động gần nhất, không tính ghim; không có phiên thì null.
export function defaultShareTarget(items: ChatSession[]): number | null {
  return [...items].sort((a, b) => lastAt(b) - lastAt(a))[0]?.id ?? null
}

// Ghim trước, rồi theo lần nhắn cuối giảm dần (máy chủ đã xếp; app xếp lại cho chắc khi gộp nhiều trang).
export function sortSessions(items: ChatSession[]): ChatSession[] {
  return [...items].sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned) || lastAt(b) - lastAt(a))
}

// Lọc tại chỗ theo tên và đoạn tin cuối (máy chủ tìm cả nội dung qua `q`), không phân biệt dấu.
export function matchSession(s: ChatSession, q: string): boolean {
  const fold = (t: string) => t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase()
  const needle = fold(q.trim())
  if (!needle) return true
  return fold(`${sessionTitle(s)} ${sessionPreview(s) ?? ''}`).includes(needle)
}

// Dòng thứ hai trong Các phiên: đoạn tin cuối, chưa có thì tóm tắt phiên.
export function sessionPreview(s: ChatSession): string | null {
  return s.last_preview?.trim() || s.summary?.trim() || null
}
