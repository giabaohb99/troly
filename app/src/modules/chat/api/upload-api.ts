import { ApiError } from '@/core/api/api-error'
import { apiPost } from '@/core/api/http-client'

// Tải tệp lên R2 bằng URL ký sẵn (12-api.md mục 5.1): xin URL, PUT thẳng lên R2, báo xong.

export const MAX_FILE_BYTES = 25 * 1024 * 1024
export const ACCEPTED_FILES = 'image/*,application/pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document'

export interface UploadedFile {
  id: number
  name: string
  mime: string
}

async function sha256Hex(file: File): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer())
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('')
}

export async function uploadFile(file: File, purpose = 'chat'): Promise<UploadedFile> {
  if (file.size > MAX_FILE_BYTES) throw new ApiError(413, 'Tệp quá 25 MB.', 'PAYLOAD_TOO_LARGE')
  const mime = file.type || 'application/octet-stream'
  const target = await apiPost<{ file_id: number; upload_url: string; upload_headers: Record<string, string> | null }>('/files/upload-url', {
    original_name: file.name,
    mime,
    size_bytes: file.size,
    purpose,
    sha256: await sha256Hex(file),
  })
  let res: Response
  try {
    res = await fetch(target.upload_url, { method: 'PUT', headers: target.upload_headers ?? { 'Content-Type': mime }, body: file })
  } catch {
    throw new ApiError(0, 'Không tải được tệp lên, kiểm tra mạng rồi thử lại.', 'NETWORK')
  }
  if (!res.ok) throw new ApiError(res.status, 'Tải tệp lên bị lỗi, thử lại.', 'UPLOAD_FAILED')
  await apiPost(`/files/${target.file_id}/complete`)
  return { id: target.file_id, name: file.name, mime }
}
