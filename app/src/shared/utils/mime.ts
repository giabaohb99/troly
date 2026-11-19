// Android thường trả mime rỗng cho .md, .txt (QĐ-44): suy theo đuôi để máy chủ nhận tệp.
const BY_EXT: Record<string, string> = {
  md: 'text/markdown',
  markdown: 'text/markdown',
  txt: 'text/plain',
  csv: 'text/csv',
  pdf: 'application/pdf',
  doc: 'application/msword',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  xls: 'application/vnd.ms-excel',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  gif: 'image/gif',
  webp: 'image/webp',
  heic: 'image/heic',
  heif: 'image/heif',
}

export function guessMime(name: string, type?: string | null): string {
  if (type && type !== 'application/octet-stream') return type
  const ext = name.toLowerCase().match(/\.([a-z0-9]+)$/)?.[1]
  return (ext && BY_EXT[ext]) || type || 'application/octet-stream'
}

export function isMarkdownFile(name: string | null | undefined, mime?: string | null): boolean {
  return mime === 'text/markdown' || /\.(md|markdown)$/i.test(name ?? '')
}
