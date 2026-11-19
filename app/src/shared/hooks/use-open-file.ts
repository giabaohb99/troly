import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { isMarkdownFile } from '@/shared/utils/mime'
import { openFileById } from '@/shared/utils/open-file'

// Mở tệp theo id: .md hiện dạng Markdown trong app (QĐ-44), còn lại tải về và mở bằng trình xem của máy.
export function useOpenFile() {
  const navigate = useNavigate()
  return useCallback(
    async (fileId: number, name?: string | null, mime?: string | null) => {
      if (isMarkdownFile(name, mime)) {
        navigate(`/xem-tep/${fileId}${name ? `?ten=${encodeURIComponent(name)}` : ''}`)
        return
      }
      await openFileById(fileId, name)
    },
    [navigate],
  )
}
