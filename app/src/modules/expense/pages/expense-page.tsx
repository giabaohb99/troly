import { useEffect, useMemo, useState } from 'react'
import { Loader2, Plus, Wallet } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { getExpense } from '@/modules/expense/api/expense-api'
import { ExpenseDialog } from '@/modules/expense/components/expense-dialog'
import { ExpenseRow } from '@/modules/expense/components/expense-row'
import { useCategories, useExpenseList, useExpenseSummary } from '@/modules/expense/hooks/use-expenses'
import type { Expense, Period } from '@/modules/expense/types/expense'
import { periodRange } from '@/modules/expense/utils/period-range'
import { EmptyState } from '@/shared/components/empty-state'
import { ErrorState } from '@/shared/components/error-state'
import { ListenerBanner } from '@/shared/components/listener-banner'
import { OfflineBanner } from '@/shared/components/offline-banner'
import { PageHeader } from '@/shared/components/page-header'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { Button } from '@/shared/ui/button'
import { formatDayTitle, formatMoney, formatMoneyShort, toDateKey } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

const PERIODS: { value: Period; label: string }[] = [
  { value: 'day', label: 'Hôm nay' },
  { value: 'week', label: 'Tuần này' },
  { value: 'month', label: 'Tháng' },
]

function SummaryCard({ period, label, active, onClick }: { period: Period; label: string; active: boolean; onClick: () => void }) {
  const summary = useExpenseSummary(period)
  return (
    <button type="button" onClick={onClick} className={cn('flex flex-col items-start rounded-2xl border bg-card px-3 py-2.5 text-left', active && 'border-primary')}>
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-lg font-bold tabular-nums">{summary.data ? formatMoneyShort(summary.data.total_expense_vnd) : '...'}</span>
      {summary.data && summary.data.total_income_vnd > 0 && <span className="text-xs text-income">+{formatMoneyShort(summary.data.total_income_vnd)}</span>}
    </button>
  )
}

// Màn Chi tiêu (31 mục 3.5): ba thẻ tổng, lọc danh mục, cần xem lại, danh sách theo ngày, ghi tay.
export function ExpensePage() {
  const [params, setParams] = useSearchParams()
  const [period, setPeriod] = useState<Period>('month')
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [editing, setEditing] = useState<{ expense: Expense | null; key: number } | null>(null)
  const range = useMemo(() => periodRange(period), [period])
  const categories = useCategories()
  const list = useExpenseList({ ...range, categoryId })
  const review = useExpenseList({ ...range, categoryId: null, needsReview: true })
  const editId = params.get('sua')

  // Mở thẳng hộp sửa khi đi từ hành động "Sửa khoản này" của trợ lý (/chi-tieu?sua=ID).
  useEffect(() => {
    if (!editId) return
    let cancelled = false
    void getExpense(Number(editId))
      .then((expense) => {
        if (!cancelled) setEditing({ expense, key: Date.now() })
      })
      .catch((error: unknown) => toast.error(getErrorMessage(error)))
      .finally(() => setParams({}, { replace: true }))
    return () => {
      cancelled = true
    }
  }, [editId, setParams])

  const items = useMemo(() => (list.data?.pages ?? []).flatMap((page) => page.items).filter((e) => !e.needs_review), [list.data])
  const reviewItems = useMemo(() => (review.data?.pages ?? []).flatMap((page) => page.items), [review.data])
  const groups = useMemo(() => {
    const map = new Map<string, Expense[]>()
    for (const expense of items) {
      const key = toDateKey(expense.spent_at)
      map.set(key, [...(map.get(key) ?? []), expense])
    }
    return [...map.entries()]
  }, [items])

  const open = (expense: Expense | null) => setEditing({ expense, key: Date.now() })

  return (
    <div className="flex flex-col gap-4 pb-8">
      <PageHeader title="Chi tiêu" subtitle={PERIODS.find((p) => p.value === period)?.label} />
      <OfflineBanner />
      <ListenerBanner text="Chưa bật đọc thông báo nên chưa tự ghi từ ngân hàng." />
      <div className="grid grid-cols-3 gap-2">
        {PERIODS.map((p) => (
          <SummaryCard key={p.value} period={p.value} label={p.label} active={period === p.value} onClick={() => setPeriod(p.value)} />
        ))}
      </div>

      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
        {[{ id: null, name: 'Tất cả' }, ...(categories.data ?? []).filter((c) => c.kind === 'expense')].map((category) => (
          <button
            key={category.id ?? 'all'}
            type="button"
            onClick={() => setCategoryId(category.id)}
            className={cn('shrink-0 rounded-full border px-3 py-1 text-sm', categoryId === category.id && 'border-primary bg-primary/15 text-primary')}
          >
            {category.name}
          </button>
        ))}
      </div>

      {reviewItems.length > 0 && (
        <section className="rounded-2xl border border-warning/40 bg-warning/5 px-3 py-2">
          <h2 className="pt-1 text-xs font-semibold tracking-wide text-warning">CẦN XEM LẠI ({reviewItems.length})</h2>
          <div className="divide-y">
            {reviewItems.map((expense) => (
              <ExpenseRow key={expense.id} expense={expense} onClick={() => open(expense)} />
            ))}
          </div>
        </section>
      )}

      {list.isPending && <SkeletonList />}
      {list.isError && <ErrorState error={list.error} onRetry={() => void list.refetch()} />}
      {list.isSuccess && items.length === 0 && reviewItems.length === 0 && (
        <EmptyState icon={Wallet} text='Chưa có khoản nào trong kỳ này. Nhắn trợ lý như "cơm trưa 45k", hoặc ghi tay.'>
          <Button size="sm" onClick={() => open(null)}>
            Ghi tay
          </Button>
        </EmptyState>
      )}

      {groups.map(([day, rows]) => (
        <section key={day}>
          <h2 className="flex justify-between text-xs font-semibold tracking-wide text-muted-foreground">
            <span>{formatDayTitle(day).toUpperCase()}</span>
            <span>{formatMoney(rows.filter((e) => e.kind === 'expense').reduce((sum, e) => sum + e.amount_vnd, 0))}</span>
          </h2>
          <div className="divide-y">
            {rows.map((expense) => (
              <ExpenseRow key={expense.id} expense={expense} onClick={() => open(expense)} />
            ))}
          </div>
        </section>
      ))}

      {list.hasNextPage && (
        <Button variant="secondary" disabled={list.isFetchingNextPage} onClick={() => void list.fetchNextPage()}>
          {list.isFetchingNextPage && <Loader2 className="size-4 animate-spin" />}
          Xem thêm
        </Button>
      )}

      <Button
        size="icon"
        aria-label="Ghi tay"
        className="fixed right-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-30 size-14 rounded-full shadow-lg"
        onClick={() => open(null)}
      >
        <Plus className="size-6" />
      </Button>

      {editing && <ExpenseDialog key={editing.key} expense={editing.expense} open onOpenChange={(value) => !value && setEditing(null)} />}
    </div>
  )
}
