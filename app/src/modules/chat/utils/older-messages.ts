import type { ChatMessage } from '@/modules/chat/types/chat'

// Ghép tin cũ đã tải thêm với 50 tin mới nhất của /chat/today; bỏ tin trùng id (cửa sổ mới nhất có thể trượt).
export function mergeOlder(older: ChatMessage[], latest: ChatMessage[]): ChatMessage[] {
  if (older.length === 0) return latest
  const ids = new Set(latest.map((m) => m.id))
  return [...older.filter((m) => !ids.has(m.id)), ...latest]
}

// Tin cũ được tải từ con trỏ `startCursor` (id tin cũ nhất của trang mới nhất lúc đó). Sau nhiều lượt chat mới,
// trang mới nhất trượt lên quá con trỏ đó thì giữa hai phần có khoảng hở: bỏ phần cũ, tải lại khi cần.
export function hasGap(startCursor: string | null, latestCursor: string | null): boolean {
  if (!startCursor || !latestCursor) return false
  return Number(latestCursor) > Number(startCursor)
}
