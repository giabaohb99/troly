import { toast } from 'sonner'
import { apiGet } from '@/core/api/http-client'
import { getErrorMessage } from '@/core/api/api-error'
import { Files } from '@/core/native/files'

// GET /files/{id} của máy chủ trả original_name (module file); name chỉ có ở API giả cũ.
interface FileInfo {
  id: number
  original_name?: string | null
  name?: string | null
  mime: string
  download_url: string
}

// Mở tệp theo id (QĐ-41): lấy link tải tạm từ GET /files/{id}, tải về máy rồi mở bằng trình xem của máy.
// Máy không có app mở được loại tệp đó thì báo và cho chia sẻ.
export async function openFileById(fileId: number, knownName?: string | null): Promise<void> {
  try {
    const info = await apiGet<FileInfo>(`/files/${fileId}`)
    // Tên tệp đúng để trình xem của máy hiện trên thanh tiêu đề (lỗi thấy trên S25+: hiện tep).
    const name = info.original_name || info.name || knownName || `tep-${fileId}`
    const result = await Files.open({ url: info.download_url, name, mime: info.mime })
    if (!result.opened && result.path) {
      const path = result.path
      toast.info('Máy chưa có app mở được tệp này.', {
        duration: 10_000,
        action: { label: 'Chia sẻ', onClick: () => void Files.share({ path, mime: info.mime }) },
      })
    }
  } catch (error) {
    toast.error(getErrorMessage(error))
  }
}

// Nhãn loại tệp cho thẻ tệp.
export function fileKindLabel(mime: string, name: string): string {
  if (mime === 'application/pdf' || name.toLowerCase().endsWith('.pdf')) return 'PDF'
  if (mime.includes('wordprocessingml') || /\.docx?$/i.test(name)) return 'Word'
  if (mime.includes('spreadsheetml') || /\.xlsx?$/i.test(name)) return 'Excel'
  if (mime.startsWith('image/')) return 'Ảnh'
  if (mime === 'text/markdown' || /\.(md|markdown)$/i.test(name)) return 'Markdown'
  return 'Tệp'
}

export function isImageFile(mime: string, name: string): boolean {
  return mime.startsWith('image/') || /\.(jpe?g|png|gif|webp|heic|heif|bmp)$/i.test(name)
}

// Rút gọn giữa, giữ đuôi tệp: "bao-cao-chi-tieu-thang-11-2026.pdf" thành "bao-cao-chi…11-2026.pdf".
export function truncateMiddle(name: string, max: number): string {
  if (name.length <= max) return name
  const dot = name.lastIndexOf('.')
  const ext = dot > 0 && name.length - dot <= 6 ? name.slice(dot) : ''
  const base = ext ? name.slice(0, dot) : name
  const keep = max - ext.length - 1
  const head = Math.ceil(keep * 0.6)
  const tail = keep - head
  return `${base.slice(0, head)}…${tail > 0 ? base.slice(-tail) : ''}${ext}`
}

export function formatFileSize(bytes: number | null | undefined): string | null {
  if (!bytes || bytes <= 0) return null
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} MB`
}
