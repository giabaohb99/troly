// Tách bảng Markdown (| a | b | rồi dòng |---|---|) khỏi chữ tin nhắn để vẽ thành bảng thật; phần còn lại giữ nguyên
// cho RichText (link, số điện thoại bấm được).

export type TextPart = { type: 'text'; value: string } | { type: 'table'; header: string[]; rows: string[][] }

const ROW = /^\s*\|.*\|\s*$/
const SEPARATOR = /^\s*\|(\s*:?-{2,}:?\s*\|)+\s*$/

function cells(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => c.trim())
}

export function splitTables(text: string): TextPart[] {
  const lines = text.split('\n')
  const parts: TextPart[] = []
  let buffer: string[] = []
  const flush = () => {
    if (buffer.length) parts.push({ type: 'text', value: buffer.join('\n') })
    buffer = []
  }
  let i = 0
  while (i < lines.length) {
    if (ROW.test(lines[i]) && i + 1 < lines.length && SEPARATOR.test(lines[i + 1])) {
      const header = cells(lines[i])
      const rows: string[][] = []
      i += 2
      while (i < lines.length && ROW.test(lines[i])) {
        const row = cells(lines[i])
        rows.push(header.map((_, j) => row[j] ?? ''))
        i += 1
      }
      // Bỏ dòng trống ngay trước bảng để khoảng cách đều.
      while (buffer.length && !buffer[buffer.length - 1].trim()) buffer.pop()
      flush()
      parts.push({ type: 'table', header, rows })
      while (i < lines.length && !lines[i].trim()) i += 1
      continue
    }
    buffer.push(lines[i])
    i += 1
  }
  flush()
  return parts
}
