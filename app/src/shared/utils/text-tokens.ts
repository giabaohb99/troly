// Tách chữ tin nhắn thành đoạn thường, in đậm, link, số điện thoại (QĐ-44: link bấm mở trình duyệt, số bấm gọi).
// Không dựng HTML: giao diện vẽ từng đoạn thành phần tử React.

export type TextToken =
  | { type: 'text'; value: string }
  | { type: 'bold'; value: string }
  | { type: 'link'; value: string; href: string }
  | { type: 'phone'; value: string; href: string }

const PATTERN = /\*\*([^*\n]+)\*\*|(https?:\/\/[^\s<>"]+|www\.[^\s<>"]+)|((?<![\d+])(?:\+84|0)(?:[ .-]?\d){8,10}(?!\d))/gi
const TRAILING = /[.,!?;:'")\]]+$/

export function tokenizeText(text: string): TextToken[] {
  const tokens: TextToken[] = []
  const push = (value: string) => {
    if (!value) return
    const prev = tokens[tokens.length - 1]
    if (prev?.type === 'text') prev.value += value
    else tokens.push({ type: 'text', value })
  }
  let last = 0
  for (const match of text.matchAll(PATTERN)) {
    const index = match.index ?? 0
    push(text.slice(last, index))
    if (match[1] !== undefined) {
      tokens.push({ type: 'bold', value: match[1] })
      last = index + match[0].length
      continue
    }
    if (match[2] !== undefined) {
      const raw = match[2]
      const trail = raw.match(TRAILING)?.[0] ?? ''
      const link = raw.slice(0, raw.length - trail.length)
      tokens.push({ type: 'link', value: link, href: link.toLowerCase().startsWith('www.') ? `https://${link}` : link })
      last = index + link.length
      continue
    }
    const phone = match[3]
    const digits = phone.replace(/\D/g, '')
    const valid = phone.startsWith('+') ? digits.length === 11 : digits.length === 10 || digits.length === 11
    if (valid) tokens.push({ type: 'phone', value: phone, href: `tel:${phone.startsWith('+') ? '+' : ''}${digits}` })
    else push(phone)
    last = index + phone.length
  }
  push(text.slice(last))
  return tokens
}
