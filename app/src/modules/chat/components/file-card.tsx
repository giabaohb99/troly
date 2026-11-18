import { useState } from 'react'
import { FileSpreadsheet, FileText, FileType, Loader2 } from 'lucide-react'
import { fileKindLabel, formatFileSize, openFileById } from '@/shared/utils/open-file'

const ICONS = { PDF: FileText, Word: FileType, Excel: FileSpreadsheet } as const

export interface FileCardData {
  file_id: number
  name: string
  mime: string
  size_bytes?: number | null
}

// Thẻ tệp bot xuất (QĐ-41): tên, loại, cỡ; bấm thì tải về và mở bằng trình xem của máy. Nhận cả hành động
// `file` (agent AI) lẫn tệp trong `attachments`.
export function FileCard({ file }: { file: FileCardData }) {
  const [busy, setBusy] = useState(false)
  const kind = fileKindLabel(file.mime, file.name)
  const Icon = ICONS[kind as keyof typeof ICONS] ?? FileText
  const size = formatFileSize(file.size_bytes)
  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => {
        setBusy(true)
        void openFileById(file.file_id, file.name).finally(() => setBusy(false))
      }}
      className="flex w-full max-w-[85%] items-center gap-3 rounded-2xl border bg-card px-3 py-2.5 text-left"
    >
      <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary">
        {busy ? <Loader2 className="size-5 animate-spin" /> : <Icon className="size-5" />}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{file.name}</span>
        <span className="block text-xs text-muted-foreground">{[kind, size].filter(Boolean).join(' · ')} · bấm để mở</span>
      </span>
    </button>
  )
}
