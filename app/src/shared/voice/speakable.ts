// Chữ để đọc to câu trả lời (1.0.6): bỏ định dạng Markdown, bỏ link, khối mã, bảng; đọc tối đa khoảng 600 ký tự,
// cắt ở cuối câu rồi nói phần còn lại để trên màn hình.

export const SPEAK_MAX_CHARS = 600
export const SPEAK_MORE = 'Chi tiết em để trên màn hình.'

export function toSpeakable(markdown: string, max = SPEAK_MAX_CHARS): string {
  const plain = markdown
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/\b(?:https?:\/\/|www\.)\S+/gi, ' ')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s*>\s?/gm, '')
    .replace(/^\s*(?:[-*+]|\d+[.)])\s+/gm, '')
    .replace(/^\s*\|?\s*:?-{3,}.*$/gm, ' ')
    .replace(/\|/g, ', ')
    .replace(/(\*\*|__)(.+?)\1/g, '$2')
    .replace(/(\*|_)([^*_\n]+)\1/g, '$2')
    .replace(/~~(.+?)~~/g, '$1')
    // Dòng xuống thành ngắt câu để giọng đọc nghỉ; gom khoảng trắng.
    .replace(/\s*\n+\s*/g, '. ')
    .replace(/([.!?,:;])\s*\.(\s|$)/g, '$1$2')
    .replace(/\s{2,}/g, ' ')
    .replace(/(^[\s.,]+)|([\s,]+$)/g, '')
    .trim()
  if (plain.length <= max) return plain
  const head = plain.slice(0, max)
  // Cắt ở cuối câu gần nhất sau nửa đoạn; không có thì cắt ở khoảng trắng.
  const sentenceEnd = Math.max(head.lastIndexOf('. '), head.lastIndexOf('! '), head.lastIndexOf('? '))
  const cut = sentenceEnd > max / 2 ? sentenceEnd + 1 : Math.max(head.lastIndexOf(' '), max / 2)
  return `${head.slice(0, cut).trim()} ${SPEAK_MORE}`
}
