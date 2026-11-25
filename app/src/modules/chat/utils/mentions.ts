// Gõ @ trong ô chat để gọi thêm (giống gắn connector trong Claude): một kết nối (ERP DEGO...), Tìm sâu, Nghĩ kỹ.
// Không gọi gì thì trợ lý tự quyết: tìm web nhanh, tự gắn kết nối khi câu nói về việc công ty.

export type MentionOption =
  | { kind: 'connector'; id: number; label: string; hint: string }
  | { kind: 'mode'; mode: 'think' | 'research'; label: string; hint: string }

export interface MentionQuery {
  // Vị trí dấu @ trong chữ.
  start: number
  query: string
}

const MODES: MentionOption[] = [
  { kind: 'mode', mode: 'research', label: 'Tìm sâu', hint: 'Tìm nhiều nguồn trên web, trả lời kỹ' },
  { kind: 'mode', mode: 'think', label: 'Nghĩ kỹ', hint: 'Suy luận kỹ cho câu khó' },
]

const fold = (s: string) =>
  s
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()

// Đang gõ dở một @: dấu @ đứng đầu hoặc sau khoảng trắng, từ @ tới con trỏ không có khoảng trắng.
export function findMention(text: string, caret: number): MentionQuery | null {
  const head = text.slice(0, caret)
  const match = head.match(/(^|\s)@([^\s@]*)$/)
  if (!match) return null
  return { start: caret - match[2].length - 1, query: match[2] }
}

export function mentionOptions(connectors: { id: number; name: string }[], query: string): MentionOption[] {
  const all: MentionOption[] = [...connectors.map((c) => ({ kind: 'connector' as const, id: c.id, label: c.name, hint: 'Tra cứu trong hệ thống này' })), ...MODES]
  const q = fold(query)
  return q ? all.filter((o) => fold(o.label).replace(/\s+/g, '').includes(q.replace(/\s+/g, ''))) : all
}

// Bỏ đoạn @truy-vấn vừa gõ khỏi chữ; trả chữ mới và vị trí con trỏ.
export function removeMention(text: string, mention: MentionQuery): { text: string; caret: number } {
  const end = mention.start + 1 + mention.query.length
  const rest = text.slice(end).replace(/^ /, '')
  return { text: text.slice(0, mention.start) + rest, caret: mention.start }
}
