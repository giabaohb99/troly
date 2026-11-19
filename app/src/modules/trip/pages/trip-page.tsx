import { useMemo, useState } from 'react'
import { Archive, ArchiveRestore, Brain, CalendarPlus, ChevronLeft, ListChecks, Navigation, FileDown, Lightbulb, Loader2, Map as MapIcon, MapPinOff, MessageCircle, MoreHorizontal, RefreshCw, Repeat, Scale, Trash2, TriangleAlert } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { Maps, maxWaypoints } from '@/core/native/maps'
import { openExternal } from '@/core/native/open-external'
import { deleteTrip, duplicateTrip, evaluateTrip, setTripArchived, exportDocx, getMapLinks, getTrip, sendToCalendar, updateTripStartDate } from '@/modules/trip/api/trip-api'
import { StopRow } from '@/modules/trip/components/stop-row'
import { ConfirmPlacesDialog, OptionsDialog, RisksDialog } from '@/modules/trip/components/trip-dialogs'
import type { Stop, Trip, TripDay } from '@/modules/trip/types/trip'
import { canNavigate, defaultDayNo, formatDuration, formatKm, groupStops, MAX_PICKED_STOPS, navigationTarget, pickedDirectionsUrl, pickedInTripOrder, risksByStop } from '@/modules/trip/utils/trip-utils'
import { ErrorState } from '@/shared/components/error-state'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { queryKeys } from '@/shared/constants/query-keys'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { formatDayTitle, toDateKey } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

const BUSY = new Set(['importing', 'evaluating'])

function dayLabel(day: TripDay): string {
  const weekday = day.weekday_text ?? (day.date ? ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'][new Date(`${day.date}T00:00:00Z`).getUTCDay()] : null)
  return weekday ? `Ngày ${day.day_no} · ${weekday}` : `Ngày ${day.day_no}`
}

function SummaryRow({ icon: Icon, text, tone, onView }: { icon: typeof MapPinOff; text: string; tone: 'warning' | 'destructive'; onView: () => void }) {
  return (
    <div className={cn('flex items-center gap-2 rounded-xl px-3 py-2 text-sm', tone === 'destructive' ? 'bg-destructive/10 text-destructive' : 'bg-warning/10 text-warning')}>
      <Icon className="size-4 shrink-0" />
      <span className="flex-1">{text}</span>
      <Button size="sm" variant="secondary" onClick={onView}>
        Xem
      </Button>
    </div>
  )
}

// Nút xem đường cả ngày: mỗi đoạn một nút, link do máy chủ dựng theo số điểm dừng tối đa (41 mục 7).
function DayRouteButtons({ tripId, dayNo }: { tripId: number; dayNo: number }) {
  const max = useQuery({ queryKey: ['maps', 'max-waypoints'], queryFn: maxWaypoints, staleTime: Infinity })
  const links = useQuery({
    queryKey: queryKeys.trip.mapLinks(tripId, dayNo, max.data ?? 3),
    queryFn: () => getMapLinks(tripId, dayNo, max.data ?? 3),
    enabled: max.isSuccess,
  })
  const urls = (links.data?.segments ?? []).flatMap((segment) => segment.urls.map((url, index) => ({ url, label: segment.segment_labels[index] })))
  if (links.isError) return <p className="text-xs text-muted-foreground">Chưa lấy được link bản đồ của ngày này.</p>
  return (
    <div className="flex flex-col gap-2">
      {urls.map(({ url, label }, index) => (
        <Button key={url} variant="outline" className="justify-start" onClick={() => void Maps.openUrl({ url }).catch(() => toast.error('Không mở được bản đồ.'))}>
          <MapIcon className="size-4" />
          {label || (urls.length > 1 ? `Xem đường cả ngày (${index + 1}/${urls.length})` : 'Xem đường cả ngày')}
        </Button>
      ))}
    </div>
  )
}

// Ngày đi do trợ lý gợi ý (thứ Bảy gần nhất): hỏi xác nhận hoặc đổi ngày; giờ các điểm dời theo.
function StartDateConfirm({ trip }: { trip: Trip }) {
  const queryClient = useQueryClient()
  const [date, setDate] = useState(trip.start_date ?? '')
  const save = useMutation({
    mutationFn: () => updateTripStartDate(trip.id, date),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.trip.detail(trip.id), updated)
      void queryClient.invalidateQueries({ queryKey: queryKeys.trip.all })
      toast.success('Đã chốt ngày đi')
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  return (
    <div className="flex flex-col gap-2 rounded-xl bg-info/10 px-3 py-2.5 text-sm">
      <span>
        Ngày đi đang là gợi ý{trip.start_date ? `: ${formatDayTitle(trip.start_date)}` : ''}. Chốt ngày để tính giờ chạy, giờ mở cửa cho đúng.
      </span>
      <div className="flex gap-2">
        <Input aria-label="Ngày đi" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        <Button size="sm" className="h-9" disabled={!date || save.isPending} onClick={() => save.mutate()}>
          {save.isPending && <Loader2 className="size-4 animate-spin" />}
          Chốt ngày
        </Button>
      </div>
    </div>
  )
}

// Mở Google Maps cho các điểm đã chọn: 1 điểm thì dẫn đường tới điểm đó; nhiều điểm thì link chỉ đường từ vị trí
// hiện tại do app dựng giống links.py (điều phối chốt không làm stop_ids ở máy chủ).
async function openPicked(chosen: Stop[]) {
  try {
    if (chosen.length === 1) {
      await Maps.navigate({ ...navigationTarget(chosen[0]), mode: 'l', avoid: 'h' })
      return
    }
    await Maps.openUrl({ url: pickedDirectionsUrl(chosen) })
  } catch {
    toast.error('Không mở được bản đồ.')
  }
}

// Chi tiết chuyến (31 mục 3.5): điểm cần xác nhận, rủi ro, theo ngày, dẫn đường xe máy, menu ba chấm.
export function TripPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const tripId = Number(useParams().tripId)
  const [params, setParams] = useSearchParams()
  const [todayKey] = useState(() => toDateKey(new Date()))
  // Chọn điểm để chỉ đường (1.0.2): tối đa 10 điểm, mở Google Maps từ vị trí hiện tại.
  const [picking, setPicking] = useState(false)
  const [picked, setPicked] = useState<Set<number>>(() => new Set())
  const [pickOpening, setPickOpening] = useState(false)
  const [panel, setPanel] = useState<'menu' | 'confirm' | 'risks' | 'options' | 'delete' | 'again' | null>(null)
  const [againDate, setAgainDate] = useState('')

  const trip = useQuery({
    queryKey: queryKeys.trip.detail(tripId),
    queryFn: () => getTrip(tripId),
    refetchInterval: (query) => (query.state.data && BUSY.has(query.state.data.status) ? 3_000 : false),
  })
  const data = trip.data
  const dayParam = Number(params.get('ngay'))
  const dayNo = data?.days.some((d) => d.day_no === dayParam) ? dayParam : defaultDayNo(data?.days ?? [], todayKey)
  const day = data?.days.find((d) => d.day_no === dayNo)
  const risks = useMemo(() => risksByStop(data?.evaluation?.risks ?? []), [data?.evaluation])
  const redCount = data?.evaluation?.risks.filter((r) => r.level === 'red').length ?? 0
  const riskCount = data?.evaluation?.risks.length ?? 0
  const chosen = data?.options.find((o) => o.id === data.chosen_option_id)
  const estimated = data?.evaluation?.estimated === true

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.trip.all })
  }
  const run = <T,>(fn: () => Promise<T>, done: (result: T) => void) =>
    fn()
      .then(done)
      .catch((error: unknown) => toast.error(getErrorMessage(error)))

  const remove = useMutation({
    mutationFn: () => deleteTrip(tripId),
    onSuccess: () => {
      toast.success('Đã xóa chuyến')
      invalidate()
      navigate('/lich-trinh', { replace: true })
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const archive = useMutation({
    mutationFn: (archived: boolean) => setTripArchived(tripId, archived),
    onSuccess: (updated, archived) => {
      queryClient.setQueryData(queryKeys.trip.detail(tripId), updated)
      invalidate()
      toast.success(archived ? 'Đã lưu trữ, chuyến nằm ở tab Đã đi' : 'Đã bỏ lưu trữ')
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  const again = useMutation({
    mutationFn: (startDate: string) => duplicateTrip(tripId, startDate),
    onSuccess: (created) => {
      setPanel(null)
      invalidate()
      toast.success('Đã tạo chuyến mới, nhớ đánh giá lại')
      navigate(`/lich-trinh/${created.id}`)
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const menu = (data: Trip) => [
    { icon: Scale, label: 'So sánh phương án', onClick: () => setPanel('options'), disabled: data.options.length === 0 },
    data.archived_at
      ? { icon: ArchiveRestore, label: 'Bỏ lưu trữ', onClick: () => archive.mutate(false), disabled: archive.isPending }
      : { icon: Archive, label: 'Đã đi xong, lưu trữ', onClick: () => archive.mutate(true), disabled: archive.isPending },
    {
      icon: Repeat,
      label: 'Đi lại',
      onClick: () => {
        setAgainDate(toDateKey(new Date(Date.now() + 7 * 86_400_000)))
        setPanel('again')
      },
    },
    ...([
      { icon: RefreshCw, label: 'Đánh giá lại', mode: 'normal' as const, done: 'Đang đánh giá lại' },
      { icon: Brain, label: 'Nghĩ kỹ (tìm giờ mở cửa trên web)', mode: 'think' as const, done: 'Đang đánh giá kỹ, lâu hơn một chút' },
    ].map((item) => ({
      icon: item.icon,
      label: item.label,
      onClick: () =>
        run(
          () => evaluateTrip(tripId, item.mode),
          () => {
            toast.success(item.done)
            invalidate()
          },
        ),
      disabled: BUSY.has(data.status),
    }))),
    { icon: CalendarPlus, label: 'Đưa vào lịch', onClick: () => run(() => sendToCalendar(tripId), (r) => toast.success(`Đã đưa ${r.event_ids.length} mục vào lịch`)) },
    { icon: FileDown, label: 'Xuất Word', onClick: () => run(() => exportDocx(tripId), (r) => void openExternal(r.download_url)) },
    { icon: MessageCircle, label: 'Hỏi trợ lý', onClick: () => navigate(`/?hoi=${encodeURIComponent(`Về chuyến ${data.title}: `)}`) },
    { icon: Trash2, label: 'Xóa chuyến', onClick: () => setPanel('delete'), danger: true },
  ]

  return (
    <div className="flex flex-col gap-4 pb-8">
      <div className="flex items-center gap-1">
        <Button size="icon" variant="ghost" aria-label="Quay lại" onClick={() => navigate('/lich-trinh')}>
          <ChevronLeft className="size-5" />
        </Button>
        <h1 className="min-w-0 flex-1 truncate text-xl font-bold">{data?.title ?? 'Chuyến đi'}</h1>
        {data && (
          <Button size="icon" variant="ghost" aria-label="Thêm thao tác" onClick={() => setPanel('menu')}>
            <MoreHorizontal className="size-5" />
          </Button>
        )}
      </div>

      {trip.isPending && <SkeletonList />}
      {trip.isError && <ErrorState error={trip.error} onRetry={() => void trip.refetch()} />}

      {data && (
        <>
          {chosen && <p className="-mt-2 text-sm text-muted-foreground">Phương án: {chosen.name}</p>}
          {data.start_date_suggested && <StartDateConfirm key={data.start_date ?? ''} trip={data} />}
          {BUSY.has(data.status) && (
            <p className="flex items-center gap-2 rounded-xl bg-secondary px-3 py-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              {data.status === 'importing' ? 'Đang đọc tệp lịch trình...' : 'Đang đánh giá giờ chạy và rủi ro...'}
            </p>
          )}
          {data.status === 'failed' && (
            <p className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{data.error ?? 'Đọc lịch trình bị lỗi.'} Hỏi trợ lý để thử lại.</p>
          )}
          {data.needs_confirmation.length > 0 && (
            <SummaryRow icon={MapPinOff} tone="warning" text={`${data.needs_confirmation.length} điểm cần xác nhận`} onView={() => setPanel('confirm')} />
          )}
          {riskCount > 0 && (
            <SummaryRow icon={TriangleAlert} tone={redCount ? 'destructive' : 'warning'} text={redCount ? `${riskCount} rủi ro, ${redCount} đỏ` : `${riskCount} điểm cần để ý`} onView={() => setPanel('risks')} />
          )}
          {data.advice && data.advice.length > 0 && (
            <div className="flex gap-2 rounded-xl border px-3 py-2 text-sm">
              <Lightbulb className="mt-0.5 size-4 shrink-0 text-primary" />
              <ul className="flex flex-col gap-1">
                {data.advice.map((line, index) => (
                  <li key={index}>{line}</li>
                ))}
              </ul>
            </div>
          )}

          {data.days.length > 0 && (
            <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
              {data.days.map((d) => (
                <button
                  key={d.day_no}
                  type="button"
                  onClick={() => setParams({ ngay: String(d.day_no) }, { replace: true })}
                  className={cn('shrink-0 rounded-full border px-3 py-1 text-sm', d.day_no === dayNo && 'border-primary bg-primary/15 text-primary', d.date === todayKey && d.day_no !== dayNo && 'border-primary/50')}
                >
                  {dayLabel(d)}
                </button>
              ))}
            </div>
          )}

          {day && (
            <section className="flex flex-col">
              {(day.title || day.total_km || day.ride_minutes) && (
                <p className="text-xs text-muted-foreground">
                  {[day.title, formatKm(day.total_km), day.ride_minutes ? `chạy ${formatDuration(day.ride_minutes)}` : null].filter(Boolean).join(' · ')}
                  {estimated && (day.total_km || day.ride_minutes) ? ' (ước tính)' : ''}
                </p>
              )}
              {day.stops.some(canNavigate) && (
                <div className="flex justify-end pt-1">
                  <Button
                    size="sm"
                    variant={picking ? 'secondary' : 'outline'}
                    onClick={() => {
                      setPicking(!picking)
                      setPicked(new Set())
                    }}
                  >
                    <ListChecks className="size-4" />
                    {picking ? 'Thôi chọn' : 'Chọn điểm'}
                  </Button>
                </div>
              )}
              <div className="divide-y">
                {groupStops(day.stops).map((stop) => (
                  <StopRow
                    key={stop.id}
                    stop={stop}
                    estimated={estimated}
                    risks={risks.get(stop.id) ?? []}
                    facts={data.facts.filter((f) => f.stop_id === stop.id)}
                    picked={picking ? (canNavigate(stop) ? picked.has(stop.id) : null) : undefined}
                    onTogglePick={() => {
                      if (!picked.has(stop.id) && picked.size >= MAX_PICKED_STOPS) {
                        toast.info(`Google Maps chỉ nhận tối đa ${MAX_PICKED_STOPS} điểm một lần`)
                        return
                      }
                      setPicked((prev) => {
                        const next = new Set(prev)
                        if (next.has(stop.id)) next.delete(stop.id)
                        else if (next.size < MAX_PICKED_STOPS) next.add(stop.id)
                        return next
                      })
                    }}
                  />
                ))}
              </div>
              {picking && (
                <div className="sticky bottom-0 -mx-4 flex gap-2 border-t bg-background px-4 py-2">
                  <Button
                    className="flex-1"
                    disabled={picked.size === 0 || pickOpening}
                    onClick={() => {
                      const chosen = pickedInTripOrder(groupStops(day.stops), picked)
                      setPickOpening(true)
                      void openPicked(chosen).finally(() => setPickOpening(false))
                    }}
                  >
                    {pickOpening ? <Loader2 className="size-4 animate-spin" /> : <Navigation className="size-4" />}
                    {picked.size <= 1 ? 'Dẫn đường' : `Chỉ đường ${picked.size} điểm`}
                  </Button>
                </div>
              )}
              {day.stops.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">Ngày này chưa có điểm nào.</p>}
            </section>
          )}

          {day && day.stops.length > 1 && !BUSY.has(data.status) && <DayRouteButtons tripId={tripId} dayNo={day.day_no} />}
          <p className="text-xs text-muted-foreground">
            {estimated ? 'Km và giờ chạy do trợ lý ước tính, chưa có số liệu Google Maps; có thể lệch.' : 'Thời gian xe máy do Google ước tính (bản thử nghiệm), có thể lệch.'}
          </p>

          <Dialog open={panel === 'menu'} onOpenChange={(open) => !open && setPanel(null)}>
            <DialogContent className="top-auto bottom-[calc(4.5rem+env(safe-area-inset-bottom))] translate-y-0">
              <DialogHeader>
                <DialogTitle>{data.title}</DialogTitle>
                <DialogDescription className="sr-only">Thao tác với chuyến</DialogDescription>
              </DialogHeader>
              <div className="flex flex-col">
                {menu(data).map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    disabled={item.disabled}
                    onClick={() => {
                      setPanel(null)
                      item.onClick()
                    }}
                    className={cn('flex items-center gap-3 rounded-xl px-2 py-3 text-left disabled:opacity-40', item.danger && 'text-destructive')}
                  >
                    <item.icon className="size-5" />
                    {item.label}
                  </button>
                ))}
              </div>
            </DialogContent>
          </Dialog>
          <ConfirmPlacesDialog trip={data} open={panel === 'confirm'} onOpenChange={(open) => setPanel(open ? 'confirm' : null)} />
          <RisksDialog trip={data} open={panel === 'risks'} onOpenChange={(open) => setPanel(open ? 'risks' : null)} />
          <OptionsDialog trip={data} open={panel === 'options'} onOpenChange={(open) => setPanel(open ? 'options' : null)} />
          <Dialog open={panel === 'again'} onOpenChange={(open) => !open && setPanel(null)}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Đi lại chuyến này</DialogTitle>
                <DialogDescription>Chép các điểm sang ngày đi mới; giờ dời theo, cần đánh giá lại.</DialogDescription>
              </DialogHeader>
              <form
                className="flex flex-col gap-3"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (againDate) again.mutate(againDate)
                }}
              >
                <Input aria-label="Ngày đi mới" type="date" value={againDate} onChange={(e) => setAgainDate(e.target.value)} required />
                <Button type="submit" disabled={!againDate || again.isPending}>
                  {again.isPending && <Loader2 className="size-4 animate-spin" />}
                  Tạo chuyến mới
                </Button>
              </form>
            </DialogContent>
          </Dialog>
          <ConfirmDialog
            open={panel === 'delete'}
            onOpenChange={(open) => setPanel(open ? 'delete' : null)}
            title="Xóa chuyến này?"
            description="Điểm, phương án và đánh giá của chuyến bị xóa. Sự kiện đã đưa vào lịch vẫn giữ."
            confirmLabel="Xóa chuyến"
            onConfirm={() => remove.mutate()}
          />
        </>
      )}
    </div>
  )
}
