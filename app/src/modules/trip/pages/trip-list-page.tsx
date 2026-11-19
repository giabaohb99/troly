import { useMemo, useState } from 'react'
import { FileUp, Link2, Loader2, MapPinOff, MessageSquareText, Plus, Route, TriangleAlert } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { listTrips, type TripScope } from '@/modules/trip/api/trip-api'
import type { TripBrief } from '@/modules/trip/types/trip'
import { formatKm, sortTrips, TRAVEL_MODE_LABEL } from '@/modules/trip/utils/trip-utils'
import { EmptyState } from '@/shared/components/empty-state'
import { ErrorState } from '@/shared/components/error-state'
import { PageHeader } from '@/shared/components/page-header'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { queryKeys } from '@/shared/constants/query-keys'
import { Button } from '@/shared/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { formatDayTitle, toDateKey } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

// Nhập lịch trình đều đi qua Chat (31 mục 3.5): trợ lý nhận tệp, link hoặc lời kể rồi gọi import.
const IMPORT_OPTIONS = [
  { icon: FileUp, label: 'Gửi tệp', text: 'Word, PDF hoặc ảnh lịch trình', prompt: 'Nhập lịch trình từ tệp em gửi kèm.' },
  { icon: Link2, label: 'Dán link', text: 'Link Google Docs, Drive hoặc trang web', prompt: 'Nhập lịch trình từ link: ' },
  { icon: MessageSquareText, label: 'Mô tả bằng lời', text: 'Kể chuyến đi, trợ lý dựng lịch trình', prompt: 'Lập lịch trình: ' },
]

function dateRange(trip: TripBrief): string | null {
  if (!trip.start_date) return null
  const start = formatDayTitle(trip.start_date).split(', ')[1]
  if (!trip.end_date || trip.end_date === trip.start_date) return start
  return `${start} tới ${formatDayTitle(trip.end_date).split(', ')[1]}`
}

function statusLine(trip: TripBrief): string | null {
  if (trip.status === 'importing') return 'Đang đọc tệp...'
  if (trip.status === 'evaluating') return 'Đang đánh giá...'
  if (trip.status === 'failed') return 'Đọc tệp lỗi, mở để xem'
  if (trip.status === 'draft') return 'Bản nháp, chưa chọn phương án'
  return null
}

function TripCard({ trip, current, onClick }: { trip: TripBrief; current: boolean; onClick: () => void }) {
  const days = trip.start_date && trip.end_date ? Math.round((Date.parse(trip.end_date) - Date.parse(trip.start_date)) / 86_400_000) + 1 : null
  const status = statusLine(trip)
  const busy = trip.status === 'importing' || trip.status === 'evaluating'
  return (
    <button type="button" onClick={onClick} className={cn('flex flex-col gap-1.5 rounded-2xl border bg-card p-4 text-left', current && 'border-primary')}>
      <span className="flex items-center gap-2">
        <span className="min-w-0 flex-1 truncate font-semibold">{trip.title}</span>
        {current && <span className="rounded-full bg-primary/15 px-2 py-0.5 text-xs text-primary">Đang đi</span>}
      </span>
      <span className="text-sm text-muted-foreground">
        {[dateRange(trip), days ? `${days} ngày` : null, TRAVEL_MODE_LABEL[trip.travel_mode], formatKm(trip.total_km)].filter(Boolean).join(' · ')}
      </span>
      {(trip.red_count > 0 || trip.yellow_count > 0 || trip.needs_confirmation_count > 0) && (
        <span className="flex flex-wrap gap-3 text-xs">
          {trip.red_count > 0 && (
            <span className="flex items-center gap-1 text-destructive">
              <TriangleAlert className="size-3.5" />
              {trip.red_count} rủi ro đỏ
            </span>
          )}
          {trip.yellow_count > 0 && (
            <span className="flex items-center gap-1 text-warning">
              <TriangleAlert className="size-3.5" />
              {trip.yellow_count} cần để ý
            </span>
          )}
          {trip.needs_confirmation_count > 0 && (
            <span className="flex items-center gap-1 text-warning">
              <MapPinOff className="size-3.5" />
              {trip.needs_confirmation_count} điểm cần xác nhận
            </span>
          )}
        </span>
      )}
      {status && (
        <span className={cn('flex items-center gap-1.5 text-xs', trip.status === 'failed' ? 'text-destructive' : 'text-muted-foreground')}>
          {busy && <Loader2 className="size-3.5 animate-spin" />}
          {status}
        </span>
      )}
    </button>
  )
}

// Danh sách chuyến (31 mục 3.5). Có chuyến đang đọc tệp hoặc đánh giá thì hỏi lại mỗi 3 giây (12 mục 5.7).
export function TripListPage() {
  const navigate = useNavigate()
  const [todayKey] = useState(() => toDateKey(new Date()))
  const [importOpen, setImportOpen] = useState(false)
  const [params, setParams] = useSearchParams()
  const scope: TripScope = params.get('tab') === 'da-di' ? 'past' : 'upcoming'
  const trips = useQuery({
    queryKey: queryKeys.trip.list(scope),
    queryFn: () => listTrips(scope),
    select: (data) => data.items,
    refetchInterval: (query) => (query.state.data?.items.some((t) => t.status === 'importing' || t.status === 'evaluating') ? 3_000 : false),
  })
  const sorted = useMemo(() => sortTrips(trips.data ?? [], todayKey), [trips.data, todayKey])
  const emptyText = scope === 'past' ? 'Chưa có chuyến nào đã đi. Chuyến qua ngày về hoặc bấm Đã đi xong sẽ vào đây.' : 'Chưa có chuyến nào. Gửi tệp lịch trình hoặc kể chuyến đi.'

  return (
    <div className="flex flex-col gap-4 pb-8">
      <PageHeader title="Lịch trình" subtitle="Chuyến đi, rủi ro, dẫn đường xe máy" />
      <div className="flex self-start rounded-full bg-secondary p-1 text-sm">
        {(
          [
            ['upcoming', 'Sắp đi'],
            ['past', 'Đã đi'],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={scope === value}
            onClick={() => setParams(value === 'past' ? { tab: 'da-di' } : {}, { replace: true })}
            className={cn('rounded-full px-4 py-1', scope === value && 'bg-background font-medium')}
          >
            {label}
          </button>
        ))}
      </div>
      {trips.isPending && <SkeletonList />}
      {trips.isError && <ErrorState error={trips.error} onRetry={() => void trips.refetch()} />}
      {trips.isSuccess && sorted.length === 0 && (
        <EmptyState icon={Route} text={emptyText}>
          <Button size="sm" onClick={() => setImportOpen(true)}>
            Nhập lịch trình
          </Button>
        </EmptyState>
      )}
      {sorted.map((trip) => {
        const current = !!trip.start_date && trip.start_date <= todayKey && todayKey <= (trip.end_date ?? trip.start_date)
        return <TripCard key={trip.id} trip={trip} current={current} onClick={() => navigate(`/lich-trinh/${trip.id}`)} />
      })}

      <Button
        size="icon"
        aria-label="Nhập lịch trình"
        className="fixed right-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-30 size-14 rounded-full shadow-lg"
        onClick={() => setImportOpen(true)}
      >
        <Plus className="size-6" />
      </Button>

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="top-auto bottom-[calc(4.5rem+env(safe-area-inset-bottom))] translate-y-0">
          <DialogHeader>
            <DialogTitle>Nhập lịch trình</DialogTitle>
            <DialogDescription>Cả ba cách đều qua trợ lý; trợ lý đọc xong thì chuyến hiện ở đây.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            {IMPORT_OPTIONS.map((option) => (
              <button
                key={option.label}
                type="button"
                onClick={() => navigate(`/?hoi=${encodeURIComponent(option.prompt)}`)}
                className="flex items-center gap-3 rounded-xl bg-secondary px-3 py-3 text-left"
              >
                <option.icon className="size-5 shrink-0 text-primary" />
                <span>
                  <span className="block font-medium">{option.label}</span>
                  <span className="block text-xs text-muted-foreground">{option.text}</span>
                </span>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
