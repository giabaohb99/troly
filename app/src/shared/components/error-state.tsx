import { RefreshCw, TriangleAlert } from 'lucide-react'
import { getErrorMessage } from '@/core/api/api-error'
import { Button } from '@/shared/ui/button'

// Thẻ lỗi tải: câu lỗi tiếng Việt của máy chủ và nút thử lại (31 mục 3.4).
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="flex w-full flex-col items-center gap-3 rounded-2xl border border-destructive/40 bg-destructive/5 px-5 py-6 text-center">
      <TriangleAlert className="size-8 text-destructive" />
      <p className="text-sm">{getErrorMessage(error)}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw className="size-4" />
          Thử lại
        </Button>
      )}
    </div>
  )
}
