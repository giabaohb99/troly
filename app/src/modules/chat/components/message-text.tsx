import type { ReactNode } from 'react'

// Chữ trả lời: giữ xuống dòng, in đậm **...**. Không dựng HTML từ chữ của AI.
export function MessageText({ text }: { text: string }) {
  const parts: ReactNode[] = []
  const pattern = /\*\*([^*]+)\*\*/g
  let last = 0
  let match: RegExpExecArray | null
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index))
    parts.push(<strong key={match.index}>{match[1]}</strong>)
    last = match.index + match[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return <>{parts}</>
}
