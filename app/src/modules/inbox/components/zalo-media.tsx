import { FileText, ImageOff, Loader2, Mic, PlayCircle, TriangleAlert } from 'lucide-react'
import type { ZaloMedia } from '@/modules/inbox/types/inbox'
import { AttachmentPreview } from '@/shared/components/attachment-preview'
import { useFileInfo } from '@/shared/hooks/use-file-info'
import { useOpenFile } from '@/shared/hooks/use-open-file'
import { formatFileSize, truncateMiddle } from '@/shared/utils/open-file'

// Ảnh, video, tệp, ghi âm trong tin Zalo (QĐ-52). Máy chủ chép tệp về kho (status pending tới khi xong); mở bằng
// GET /files/{file_id}. Ảnh xem nhỏ, bấm mở lớn; video, tệp mở bằng trình xem của máy; ghi âm nghe ngay.
export function ZaloMediaView({ media }: { media: ZaloMedia }) {
  if (media.status === 'pending' || !media.file_id) {
    return (
      <span className="flex items-center gap-2 text-xs text-muted-foreground">
        {media.status === 'failed' ? <TriangleAlert className="size-3.5 text-warning" /> : <Loader2 className="size-3.5 animate-spin" />}
        {media.status === 'failed' ? 'Không lấy được tệp từ Zalo' : `Đang lấy ${LABEL[media.type]}...`}
      </span>
    )
  }
  if (media.status === 'failed') {
    return (
      <span className="flex items-center gap-2 text-xs text-warning">
        <TriangleAlert className="size-3.5" />
        Không lấy được {LABEL[media.type]}
      </span>
    )
  }
  if (media.type === 'image') return <ZaloImage fileId={media.file_id} name={media.name} />
  if (media.type === 'voice') return <ZaloVoice fileId={media.file_id} />
  if (media.type === 'video') return <ZaloVideo fileId={media.file_id} name={media.name} size={media.size} />
  return <AttachmentPreview attachment={{ file_id: media.file_id, name: media.name, mime: media.mime, size_bytes: media.size }} />
}

const LABEL: Record<ZaloMedia['type'], string> = { image: 'ảnh', video: 'video', file: 'tệp', voice: 'ghi âm' }

function ZaloImage({ fileId, name }: { fileId: number; name: string | null }) {
  const info = useFileInfo(fileId)
  const openFile = useOpenFile()
  if (info.isError) return <ImageOff className="size-6 text-muted-foreground" aria-label="Không tải được ảnh" />
  if (!info.data) return <span className="block size-40 animate-pulse rounded-xl bg-muted" />
  return (
    <button type="button" onClick={() => void openFile(fileId, name ?? info.data.original_name, info.data.mime)} className="block">
      <img src={info.data.download_url ?? undefined} alt={name ?? 'Ảnh Zalo'} className="max-h-60 max-w-[220px] rounded-xl object-cover" loading="lazy" />
    </button>
  )
}

function ZaloVideo({ fileId, name, size }: { fileId: number; name: string | null; size: number | null }) {
  const openFile = useOpenFile()
  return (
    <button type="button" onClick={() => void openFile(fileId, name ?? 'video.mp4', 'video/mp4')} className="flex items-center gap-2 rounded-xl border bg-card px-3 py-2 text-left">
      <PlayCircle className="size-8 shrink-0 text-primary" />
      <span className="min-w-0">
        <span className="block text-xs font-medium">{truncateMiddle(name ?? 'Video', 24)}</span>
        <span className="block text-[11px] text-muted-foreground">{['Video', formatFileSize(size ?? 0)].filter(Boolean).join(' · ')}</span>
      </span>
    </button>
  )
}

function ZaloVoice({ fileId }: { fileId: number }) {
  const info = useFileInfo(fileId)
  if (!info.data)
    return (
      <span className="flex items-center gap-2 text-xs text-muted-foreground">
        <Mic className="size-3.5" />
        Ghi âm
      </span>
    )
  return <audio controls preload="none" src={info.data.download_url ?? undefined} className="h-10 max-w-[240px]" aria-label="Ghi âm Zalo" />
}

export function PendingFileChip({ name }: { name: string }) {
  return (
    <span className="flex items-center gap-1.5 text-xs opacity-80">
      <FileText className="size-3.5" />
      {truncateMiddle(name, 24)}
    </span>
  )
}
