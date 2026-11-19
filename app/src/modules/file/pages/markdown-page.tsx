import { ChevronLeft, Download } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { apiGet } from '@/core/api/http-client'
import { ErrorState } from '@/shared/components/error-state'
import { MarkdownView } from '@/shared/components/markdown-view'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { Button } from '@/shared/ui/button'
import { openFileById } from '@/shared/utils/open-file'

const MAX_CHARS = 500_000

// Xem tệp .md trong app (QĐ-44): tải chữ qua link tải tạm rồi vẽ Markdown; nút tải về để mở bằng app khác.
export function MarkdownPage() {
  const navigate = useNavigate()
  const fileId = Number(useParams().fileId)
  const name = useSearchParams()[0].get('ten')
  const content = useQuery({
    queryKey: ['file', fileId, 'text'],
    queryFn: async () => {
      const info = await apiGet<{ original_name: string | null; download_url: string }>(`/files/${fileId}`)
      const res = await fetch(info.download_url)
      if (!res.ok) throw new Error('Không tải được tệp.')
      const text = await res.text()
      return { name: info.original_name ?? name ?? 'Tệp', text: text.length > MAX_CHARS ? `${text.slice(0, MAX_CHARS)}\n\n…` : text }
    },
    staleTime: 4 * 60_000,
  })

  return (
    <div className="flex flex-col gap-4 pb-8">
      <div className="flex items-center gap-1">
        <Button size="icon" variant="ghost" aria-label="Quay lại" onClick={() => navigate(-1)}>
          <ChevronLeft className="size-5" />
        </Button>
        <h1 className="min-w-0 flex-1 truncate text-lg font-bold">{content.data?.name ?? name ?? 'Tệp'}</h1>
        <Button size="icon" variant="ghost" aria-label="Mở bằng app khác" onClick={() => void openFileById(fileId, content.data?.name ?? name)}>
          <Download className="size-5" />
        </Button>
      </div>
      {content.isPending && <SkeletonList />}
      {content.isError && <ErrorState error={content.error} onRetry={() => void content.refetch()} />}
      {content.data && (
        <article className="rounded-2xl border bg-card p-4">
          <MarkdownView source={content.data.text} />
        </article>
      )}
    </div>
  )
}
