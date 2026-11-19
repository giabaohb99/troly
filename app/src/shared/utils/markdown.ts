// Trình đọc Markdown gọn cho tệp .md (QĐ-44): chỉ tách khối và đoạn chữ, giao diện tự vẽ thành phần tử React,
// không dựng HTML nên không có đường chèn script. Đủ cho ghi chú: tiêu đề, đoạn, danh sách, trích dẫn, mã, kẻ ngang.

export type InlineToken =
  | { type: 'text'; value: string }
  | { type: 'strong'; value: string }
  | { type: 'em'; value: string }
  | { type: 'code'; value: string }
  | { type: 'link'; value: string; href: string }

export type Block =
  | { type: 'heading'; level: number; text: string }
  | { type: 'paragraph'; text: string }
  | { type: 'list'; ordered: boolean; items: string[] }
  | { type: 'quote'; text: string }
  | { type: 'code'; lang: string | null; text: string }
  | { type: 'hr' }

export function parseMarkdown(source: string): Block[] {
  const lines = source.replace(/\r\n?/g, '\n').split('\n')
  const blocks: Block[] = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) {
      i++
      continue
    }
    const fence = line.match(/^\s*```\s*([\w-]+)?\s*$/)
    if (fence) {
      const body: string[] = []
      i++
      while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) body.push(lines[i++])
      i++
      blocks.push({ type: 'code', lang: fence[1] ?? null, text: body.join('\n') })
      continue
    }
    const heading = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/)
    if (heading) {
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2] })
      i++
      continue
    }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
      blocks.push({ type: 'hr' })
      i++
      continue
    }
    if (/^\s*>/.test(line)) {
      const body: string[] = []
      while (i < lines.length && /^\s*>/.test(lines[i])) body.push(lines[i++].replace(/^\s*>\s?/, ''))
      blocks.push({ type: 'quote', text: body.join('\n') })
      continue
    }
    const bullet = /^\s*[-*+]\s+/
    const numbered = /^\s*\d+[.)]\s+/
    if (bullet.test(line) || numbered.test(line)) {
      const ordered = numbered.test(line)
      const pattern = ordered ? numbered : bullet
      const items: string[] = []
      while (i < lines.length && pattern.test(lines[i])) items.push(lines[i++].replace(pattern, ''))
      blocks.push({ type: 'list', ordered, items })
      continue
    }
    const body: string[] = []
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|\s*```|\s*>|\s*[-*+]\s|\s*\d+[.)]\s)/.test(lines[i])) body.push(lines[i++])
    if (body.length === 0) body.push(lines[i++])
    blocks.push({ type: 'paragraph', text: body.join('\n') })
  }
  return blocks
}

const INLINE = /`([^`]+)`|\*\*([^*]+)\*\*|__([^_]+)__|\*([^*\s][^*]*)\*|_([^_\s][^_]*)_|\[([^\]]+)\]\(([^)\s]+)\)/g

export function parseInline(text: string): InlineToken[] {
  const tokens: InlineToken[] = []
  let last = 0
  for (const m of text.matchAll(INLINE)) {
    const index = m.index ?? 0
    if (index > last) tokens.push({ type: 'text', value: text.slice(last, index) })
    if (m[1] !== undefined) tokens.push({ type: 'code', value: m[1] })
    else if (m[2] !== undefined || m[3] !== undefined) tokens.push({ type: 'strong', value: m[2] ?? m[3] })
    else if (m[4] !== undefined || m[5] !== undefined) tokens.push({ type: 'em', value: m[4] ?? m[5] })
    else if (/^(https?:|mailto:|tel:)/i.test(m[7])) tokens.push({ type: 'link', value: m[6], href: m[7] })
    else tokens.push({ type: 'text', value: m[6] })
    last = index + m[0].length
  }
  if (last < text.length) tokens.push({ type: 'text', value: text.slice(last) })
  return tokens
}
