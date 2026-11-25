// Tách chữ tin nhắn thành đoạn thường, in đậm, link, số điện thoại, email (link bấm mở trình duyệt, số bấm gọi,
// email bấm soạn thư).
// Không dựng HTML: giao diện vẽ từng đoạn thành phần tử React.

export type TextToken =
  | { type: 'text'; value: string }
  | { type: 'bold'; value: string }
  | { type: 'link'; value: string; href: string }
  | { type: 'phone'; value: string; href: string }
  | { type: 'email'; value: string; href: string }

// Thứ tự nhóm: in đậm, link (nuốt cả email nằm trong link), email, số điện thoại.
const PATTERN =
  /\*\*([^*\n]+)\*\*|(https?:\/\/[^\s<>"]+|www\.[^\s<>"]+)|([\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,})|((?<![\d+])(?:(?:\+84|0)(?:[ .-]?\d){8,10}|1[89]00(?:[ .-]?\d){4,6})(?!\d))/gi
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
    if (match[3] !== undefined) {
      tokens.push({ type: 'email', value: match[3], href: `mailto:${match[3]}` })
      last = index + match[3].length
      continue
    }
    const phone = match[4]
    const digits = phone.replace(/\D/g, '')
    // Tổng đài 1800, 1900: 8 hoặc 10 chữ số.
    const hotline = /^1[89]00/.test(digits)
    const valid = phone.startsWith('+') ? digits.length === 11 : hotline ? digits.length === 8 || digits.length === 10 : digits.length === 10 || digits.length === 11
    if (valid) tokens.push({ type: 'phone', value: phone, href: `tel:${phone.startsWith('+') ? '+' : ''}${digits}` })
    else push(phone)
    last = index + phone.length
  }
  push(text.slice(last))
  return tokens
}

// Nhãn ngắn của link dài (phản hồi 1.0.8): tên miền, bỏ www. (https://dashboard.render.com/... thành dashboard.render.com).
export const LONG_LINK_CHARS = 40

export function linkHost(href: string): string {
  try {
    return new URL(href).hostname.replace(/^www\./i, '')
  } catch {
    return href.replace(/^https?:\/\//i, '').split(/[/?#]/)[0].replace(/^www\./i, '')
  }
}

/**
 * Thư dạng chữ hay bị ngắt dòng cứng ở khoảng 70 ký tự. Gộp dòng bị ngắt giữa câu vào dòng sau, giữ xuống dòng thật:
 * dòng trống (hết đoạn), dòng kết câu, dòng ngắn (lời chào, chữ ký), gạch đầu dòng, trích dẫn.
 */
export function reflowPlainText(text: string): string {
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  const out: string[] = []
  const listOrQuote = /^\s*(?:[-*•>]|\d+[.)])\s/
  for (const raw of lines) {
    const line = raw.replace(/\s+$/, '')
    const prev = out[out.length - 1]
    const joinable =
      prev !== undefined &&
      prev.trim() !== '' &&
      line.trim() !== '' &&
      prev.length >= 40 &&
      !/[.!?:;。]["')\]]?$/.test(prev) &&
      !listOrQuote.test(line) &&
      !/^\s*>/.test(prev)
    if (joinable) out[out.length - 1] = `${prev} ${line.trim()}`
    else out.push(line)
  }
  // Tối đa một dòng trống liền nhau.
  return out.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

