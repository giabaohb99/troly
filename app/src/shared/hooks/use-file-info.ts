import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/core/api/http-client'

// Thông tin một tệp (GET /files/{id}): tên, loại, cỡ, link tải tạm (hạn 300 giây). Tin người dùng chỉ có file_id
// nên thẻ đính kèm hỏi thêm ở đây; giữ 4 phút cho link chưa hết hạn.
export interface FileInfo {
  id: number
  original_name: string | null
  mime: string
  size_bytes: number | null
  download_url?: string | null
}

export function useFileInfo(fileId: number, enabled = true) {
  return useQuery({
    queryKey: ['file', fileId],
    queryFn: () => apiGet<FileInfo>(`/files/${fileId}`),
    staleTime: 4 * 60_000,
    gcTime: 10 * 60_000,
    enabled,
    retry: 1,
  })
}
