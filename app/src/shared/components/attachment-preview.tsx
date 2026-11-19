import { useState } from 'react'
import { FileSpreadsheet, FileText, FileType, ImageOff, Loader2 } from 'lucide-react'
import { useFileInfo } from '@/shared/hooks/use-file-info'
import { useOpenFile } from '@/shared/hooks/use-open-file'
import { fileKindLabel, formatFileSize, isImageFile, truncateMiddle } from '@/shared/utils/open-file'
import { cn } from '@/shared/utils/cn'

const ICONS = { PDF: FileText, Word: FileType, Excel: FileSpreadsheet } as const

// Tệp gửi kèm tin (chat, Hộp tin): có thể chỉ có file_id, thiếu thì hỏi thêm GET /files/{id}.
export interface AttachmentRef {
  file_id: number
  mime?: string | null
  name?: string | null
  size_bytes?: number | null
}

// Tệp người dùng gửi kèm (lỗi bản 1.0.1: chỉ hiện biểu tượng nhỏ). Ảnh: ảnh thu nhỏ bo góc, tối đa 200 px, bấm xem
// lớn bằng trình xem của máy. Tệp khác: thẻ nhỏ có biểu tượng loại, tên rút gọn giữa, cỡ, bấm mở.
// Máy chủ chỉ gửi file_id thì hỏi GET /files/{id} cho tên, loại, cỡ, link tải.
export function AttachmentPreview({ attachment }: { attachment: AttachmentRef }) {
  const needInfo = !attachment.mime || !attachment.name || isImageFile(attachment.mime, attachment.name)
  const info = useFileInfo(attachment.file_id, needInfo)
  const [opening, setOpening] = useState(false)
  const openFile = useOpenFile()
  const [broken, setBroken] = useState(false)
  const name = attachment.name ?? info.data?.original_name ?? 'Tệp'
  const mime = attachment.mime ?? info.data?.mime ?? ''
  const size = attachment.size_bytes ?? info.data?.size_bytes ?? null
  const open = () => {
    setOpening(true)
    void openFile(attachment.file_id, name, mime).finally(() => setOpening(false))
  }

  if (!mime && needInfo && info.isPending) {
    return <span className="block h-12 w-40 animate-pulse rounded-xl bg-secondary" aria-label="Đang tải tệp" />
  }

  if (isImageFile(mime, name)) {
    const url = info.data?.download_url
    return (
      <button type="button" onClick={open} aria-label={`Xem ảnh ${name}`} className="relative overflow-hidden rounded-2xl bg-secondary">
        {url && !broken ? (
          <img
            src={url}
            alt={name}
            loading="lazy"
            onError={() => {
              // Link tải tạm hết hạn: hỏi lại một lần.
              if (!info.isFetching) void info.refetch().then((r) => r.isError && setBroken(true))
              else setBroken(true)
            }}
            className="block max-h-[200px] max-w-[200px] object-cover"
          />
        ) : (
          <span className={cn('flex size-32 items-center justify-center text-muted-foreground', info.isPending && 'animate-pulse')}>
            {info.isPending ? null : <ImageOff className="size-6" />}
          </span>
        )}
        {opening && (
          <span className="absolute inset-0 flex items-center justify-center bg-background/50">
            <Loader2 className="size-5 animate-spin" />
          </span>
        )}
      </button>
    )
  }

  const kind = fileKindLabel(mime, name)
  const Icon = ICONS[kind as keyof typeof ICONS] ?? FileText
  return (
    <button type="button" onClick={open} className="flex max-w-[240px] items-center gap-2 rounded-xl border bg-card px-2.5 py-2 text-left">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
        {opening ? <Loader2 className="size-4 animate-spin" /> : <Icon className="size-4" />}
      </span>
      <span className="min-w-0">
        <span className="block text-xs font-medium" title={name}>
          {truncateMiddle(name, 26)}
        </span>
        <span className="block text-[11px] text-muted-foreground">{[kind, formatFileSize(size)].filter(Boolean).join(' · ')}</span>
      </span>
    </button>
  )
}
