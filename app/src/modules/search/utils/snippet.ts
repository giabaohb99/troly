// Đoạn trích của máy chủ (ts_headline) chỉ có thẻ <b>. Tách thành đoạn thường và đoạn in đậm,
// không dùng dangerouslySetInnerHTML; thẻ lạ và thực thể HTML được bỏ hoặc giải mã.
export interface SnippetPart {
  text: string
  bold: boolean
}

const ENTITIES: Record<string, string> = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&nbsp;': ' ' }

function decode(text: string): string {
  return text.replace(/<(?!\/?b>)[^>]*>/gi, '').replace(/&(amp|lt|gt|quot|#39|nbsp);/g, (m) => ENTITIES[m] ?? m)
}

export function splitSnippet(snippet: string): SnippetPart[] {
  const parts: SnippetPart[] = []
  const pattern = /<b>([\s\S]*?)<\/b>/gi
  let last = 0
  let match: RegExpExecArray | null
  while ((match = pattern.exec(snippet)) !== null) {
    if (match.index > last) parts.push({ text: decode(snippet.slice(last, match.index)), bold: false })
    parts.push({ text: decode(match[1]), bold: true })
    last = match.index + match[0].length
  }
  if (last < snippet.length) parts.push({ text: decode(snippet.slice(last)), bold: false })
  return parts.filter((p) => p.text)
}
