// Gõ @ trong ô chat để gọi một đoạn chat khác vào (QĐ-58): lượt này trợ lý đọc thêm tóm tắt và tin gần đây của
// đoạn đó. Kết nối (ERP...) trợ lý tự gắn khi câu nói về việc công ty; muốn kỹ hơn thì gõ *nghĩ kỹ*, *tìm trên mạng*.

export interface MentionOption {
  id: number
  label: string
  hint: string
}

export interface MentionQuery {
  // Vị trí dấu @ trong chữ.
  start: number
  query: string
}

const fold = (s: string) =>
  s
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/\s+/g, '')

// Đang gõ dở một @: dấu @ đứng đầu hoặc sau khoảng trắng, từ @ tới con trỏ không có khoảng trắng.
export function findMention(text: string, caret: number): MentionQuery | null {
  const head = text.slice(0, caret)
  const match = head.match(/(^|\s)@([^\s@]*)$/)
  if (!match) return null
  return { start: caret - match[2].length - 1, query: match[2] }
}

// Lọc không dấu theo tên đoạn chat; tối đa 6 dòng cho vừa màn hình khi bàn phím mở.
export function mentionOptions(sessions: MentionOption[], query: string): MentionOption[] {
  const q = fold(query)
  return (q ? sessions.filter((o) => fold(o.label).includes(q)) : sessions).slice(0, 6)
}

// Bỏ đoạn @truy-vấn vừa gõ khỏi chữ; trả chữ mới và vị trí con trỏ.
export function removeMention(text: string, mention: MentionQuery): { text: string; caret: number } {
  const end = mention.start + 1 + mention.query.length
  const rest = text.slice(end).replace(/^ /, '')
  return { text: text.slice(0, mention.start) + rest, caret: mention.start }
}
