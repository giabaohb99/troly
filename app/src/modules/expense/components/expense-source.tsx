import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/core/api/http-client'
import { formatTime } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

interface ExpenseSource {
  app_package: string
  title: string | null
  text: string | null
  posted_at: string
}

// Thông báo gốc của dòng tự ghi từ ngân hàng, để đối chiếu (31 mục 3.5). Quá 180 ngày thì máy chủ trả 404.
export function ExpenseSourceBlock({ expenseId }: { expenseId: number }) {
  const [open, setOpen] = useState(false)
  const source = useQuery({
    queryKey: ['expense', 'source', expenseId],
    queryFn: () => apiGet<ExpenseSource>(`/expenses/${expenseId}/source`),
    enabled: open,
    retry: 0,
  })
  return (
    <div className="rounded-xl bg-secondary p-3 text-sm">
      <button type="button" onClick={() => setOpen((v) => !v)} className="flex w-full items-center justify-between text-muted-foreground">
        Thông báo gốc
        <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="mt-2">
          {source.isPending && <p className="text-muted-foreground">Đang tải...</p>}
          {source.isError && <p className="text-muted-foreground">Thông báo gốc không còn (giữ 180 ngày).</p>}
          {source.data && (
            <>
              <p className="font-medium">
                {source.data.title} · {formatTime(source.data.posted_at)}
              </p>
              <p className="whitespace-pre-wrap break-words">{source.data.text}</p>
            </>
          )}
        </div>
      )}
    </div>
  )
}
