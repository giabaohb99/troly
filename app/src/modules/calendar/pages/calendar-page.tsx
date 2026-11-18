import { useEffect, useMemo, useState } from 'react'
import { BellOff, CalendarDays, ChevronLeft, ChevronRight, CloudOff, ListTodo, Loader2, Plus, RefreshCw, TriangleAlert } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { apiPost } from '@/core/api/http-client'
import { getErrorMessage } from '@/core/api/api-error'
import { isNative } from '@/core/config'
import { System } from '@/core/native/system'
import { getEvent, getTask } from '@/modules/calendar/api/calendar-api'
import { EventRow, TaskRow } from '@/modules/calendar/components/calendar-rows'
import { EventDialog } from '@/modules/calendar/components/event-dialog'
import { TaskDialog } from '@/modules/calendar/components/task-dialog'
import { useEvents, useTasks } from '@/modules/calendar/hooks/use-calendar'
import type { CalendarEvent, CalendarView, Task } from '@/modules/calendar/types/calendar'
import { addDays, eventsByDay, groupTasks, monthGridKeys, taskDueKey, viewRange, weekKeys } from '@/modules/calendar/utils/calendar-dates'
import { EmptyState } from '@/shared/components/empty-state'
import { ErrorState } from '@/shared/components/error-state'
import { OfflineBanner } from '@/shared/components/offline-banner'
import { PageHeader } from '@/shared/components/page-header'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { queryKeys } from '@/shared/constants/query-keys'
import { needsReconnect, useGoogleStatus } from '@/shared/hooks/use-google-status'
import { usePermissions } from '@/shared/hooks/use-permissions'
import { Button } from '@/shared/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { formatDayTitle, formatTime, toDateKey } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

const VIEWS: { value: CalendarView; label: string; param: string }[] = [
  { value: 'day', label: 'Ngày', param: 'ngay' },
  { value: 'week', label: 'Tuần', param: 'tuan' },
  { value: 'month', label: 'Tháng', param: 'thang' },
]
const WEEKDAY_SHORT = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

type Editing = { kind: 'event'; event: CalendarEvent | null; key: number } | { kind: 'task'; task: Task | null; key: number } | null

function Banner({ icon: Icon, text, action, onAction, tone = 'warning' }: { icon: typeof BellOff; text: string; action: string; onAction: () => void; tone?: 'warning' | 'info' }) {
  return (
    <div className={cn('flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm', tone === 'warning' ? 'bg-warning/10 text-warning' : 'bg-info/10')}>
      <Icon className="size-4 shrink-0" />
      <span className="min-w-0 flex-1">{text}</span>
      <Button size="sm" variant="secondary" onClick={onAction}>
        {action}
      </Button>
    </div>
  )
}

// Màn Lịch và việc (31 mục 3.5): Ngày, Tuần, Tháng; danh sách việc; thêm sự kiện hoặc việc.
// Đường dẫn sâu từ thông báo nhắc: /lich/su-kien/:id (?lan=<lần lặp>) và /lich/viec/:id.
export function CalendarPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { eventId, taskId } = useParams()
  const [params, setParams] = useSearchParams()
  const [todayKey] = useState(() => toDateKey(new Date()))
  const [editing, setEditing] = useState<Editing>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const dayParam = params.get('ngay')
  const dayKey = dayParam && DATE_RE.test(dayParam) ? dayParam : todayKey
  const view = VIEWS.find((v) => v.param === params.get('xem'))?.value ?? 'day'
  const tab = params.get('tab') === 'viec' || taskId ? 'tasks' : 'calendar'
  const range = useMemo(() => viewRange(view, dayKey), [view, dayKey])

  const events = useEvents(range)
  const todo = useTasks('todo')
  const done = useTasks('done')
  const google = useGoogleStatus()
  const permissions = usePermissions()

  const byDay = useMemo(() => eventsByDay((events.data ?? []).filter((e) => e.task_id === null)), [events.data])
  const groups = useMemo(() => groupTasks([...(todo.data ?? []), ...(done.data ?? [])], todayKey), [todo.data, done.data, todayKey])
  const tasksByDay = useMemo(() => {
    const map = new Map<string, Task[]>()
    for (const task of todo.data ?? []) {
      const key = taskDueKey(task)
      if (key) map.set(key, [...(map.get(key) ?? []), task])
    }
    return map
  }, [todo.data])
  const dueCount = groups.overdue.length + groups.today.length

  // Mở thẳng hộp sửa khi đến từ thông báo nhắc hoặc hành động open_screen.
  const occurrenceParam = params.get('lan')
  useEffect(() => {
    if (!eventId && !taskId) return
    let cancelled = false
    const load = eventId
      ? getEvent(Number(eventId), occurrenceParam).then((event) => !cancelled && setEditing({ kind: 'event', event, key: Date.now() }))
      : getTask(Number(taskId)).then((task) => !cancelled && setEditing({ kind: 'task', task, key: Date.now() }))
    void load.catch((error: unknown) => toast.error(getErrorMessage(error)))
    return () => {
      cancelled = true
    }
  }, [eventId, taskId, occurrenceParam])

  const setParam = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(eventId || taskId ? '' : params)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null) next.delete(key)
      else next.set(key, value)
    }
    if (eventId || taskId) navigate(`/lich?${next.toString()}`, { replace: true })
    else setParams(next, { replace: true })
  }

  const closeEditing = () => {
    setEditing(null)
    if (eventId || taskId) navigate(tab === 'tasks' ? '/lich?tab=viec' : '/lich', { replace: true })
  }

  async function refresh() {
    setRefreshing(true)
    try {
      if (google.data?.connected) {
        const packs = google.data.packs.filter((p) => p.enabled && (p.name === 'calendar' || p.name === 'tasks'))
        await Promise.all(packs.map((p) => apiPost(`/google/sync/${p.name}`)))
        // Máy chủ đồng bộ nền; chờ một nhịp rồi tải lại.
        await new Promise((resolve) => setTimeout(resolve, 2_500))
      }
      await queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all })
      await queryClient.invalidateQueries({ queryKey: queryKeys.google.status })
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setRefreshing(false)
    }
  }

  const calendarPack = google.data?.packs.find((p) => p.name === 'calendar')
  const subtitle = !google.data
    ? undefined
    : !google.data.connected
      ? 'Chỉ trên app, chưa nối Google'
      : google.data.initial_sync.state === 'running' || google.data.initial_sync.state === 'pending'
        ? google.data.initial_sync.message
        : calendarPack?.last_sync_at
          ? `Google Calendar · đồng bộ ${formatTime(calendarPack.last_sync_at)}`
          : 'Google Calendar'

  const weekStrip = weekKeys(dayKey)

  return (
    <div className="flex flex-col gap-4 pb-8">
      <PageHeader
        title="Lịch"
        subtitle={subtitle}
        actions={
          <Button size="icon" variant="ghost" aria-label="Đồng bộ lại" disabled={refreshing} onClick={() => void refresh()}>
            {refreshing ? <Loader2 className="size-5 animate-spin" /> : <RefreshCw className="size-5" />}
          </Button>
        }
      />
      <OfflineBanner />
      {isNative && permissions.data && !permissions.data.notifications && (
        <Banner icon={BellOff} text="Nhắc sẽ không kêu vì thông báo đang tắt." action="Bật" onAction={() => void System.requestNotifications()} />
      )}
      {google.isSuccess && !google.data.connected && (
        <Banner icon={CloudOff} tone="info" text="Kết nối Google Calendar để thấy lịch ở đây." action="Kết nối" onAction={() => navigate('/cai-dat/google')} />
      )}
      {needsReconnect(google.data) && <Banner icon={CloudOff} text="Cần kết nối lại Google." action="Kết nối lại" onAction={() => navigate('/cai-dat/google')} />}
      {!!google.data?.failed_outbox_count && (
        <Banner icon={TriangleAlert} text={`${google.data.failed_outbox_count} thay đổi chưa lên được Google.`} action="Xem" onAction={() => navigate('/cai-dat/google')} />
      )}

      <div className="flex items-center gap-2">
        <div className="flex rounded-full bg-secondary p-1 text-sm">
          <button type="button" onClick={() => setParam({ tab: null })} className={cn('flex items-center gap-1.5 rounded-full px-3 py-1', tab === 'calendar' && 'bg-background font-medium')}>
            <CalendarDays className="size-4" />
            Lịch
          </button>
          <button type="button" onClick={() => setParam({ tab: 'viec' })} className={cn('flex items-center gap-1.5 rounded-full px-3 py-1', tab === 'tasks' && 'bg-background font-medium')}>
            <ListTodo className="size-4" />
            Việc{dueCount > 0 && <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground">{dueCount}</span>}
          </button>
        </div>
        {tab === 'calendar' && (
          <div className="ml-auto flex rounded-full border p-0.5 text-xs">
            {VIEWS.map((v) => (
              <button key={v.value} type="button" onClick={() => setParam({ xem: v.value === 'day' ? null : v.param })} className={cn('rounded-full px-2.5 py-1', view === v.value && 'bg-primary/15 text-primary')}>
                {v.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {tab === 'calendar' && (
        <>
          {(view === 'day' || view === 'week') && (
            <div className="flex items-center gap-1">
              <Button size="icon" variant="ghost" aria-label="Tuần trước" onClick={() => setParam({ ngay: addDays(dayKey, -7) })}>
                <ChevronLeft className="size-4" />
              </Button>
              <div className="grid flex-1 grid-cols-7 text-center">
                {weekStrip.map((key, index) => (
                  <button key={key} type="button" onClick={() => setParam({ ngay: key, xem: null })} className="flex flex-col items-center gap-0.5 py-1">
                    <span className="text-[11px] text-muted-foreground">{WEEKDAY_SHORT[index]}</span>
                    <span
                      className={cn(
                        'flex size-8 items-center justify-center rounded-full text-sm tabular-nums',
                        key === todayKey && 'text-primary',
                        key === dayKey && view === 'day' && 'bg-primary font-semibold text-primary-foreground',
                      )}
                    >
                      {Number(key.slice(8))}
                    </span>
                    <span className={cn('size-1 rounded-full', byDay.has(key) || tasksByDay.has(key) ? 'bg-muted-foreground' : 'bg-transparent')} />
                  </button>
                ))}
              </div>
              <Button size="icon" variant="ghost" aria-label="Tuần sau" onClick={() => setParam({ ngay: addDays(dayKey, 7) })}>
                <ChevronRight className="size-4" />
              </Button>
            </div>
          )}

          {view === 'month' && (
            <MonthGrid dayKey={dayKey} todayKey={todayKey} byDay={byDay} tasksByDay={tasksByDay} onPick={(key) => setParam({ ngay: key, xem: null })} onMove={(months) => setParam({ ngay: shiftMonth(dayKey, months) })} />
          )}

          {events.isPending && <SkeletonList />}
          {events.isError && <ErrorState error={events.error} onRetry={() => void events.refetch()} />}

          {events.isSuccess && view === 'day' && (
            <DaySection
              dayKey={dayKey}
              todayKey={todayKey}
              events={byDay.get(dayKey) ?? []}
              tasks={tasksByDay.get(dayKey) ?? []}
              onEvent={(event) => setEditing({ kind: 'event', event, key: Date.now() })}
              onTask={(task) => setEditing({ kind: 'task', task, key: Date.now() })}
              showEmpty
            />
          )}
          {events.isSuccess &&
            view === 'week' &&
            weekStrip.map((key) => (
              <DaySection
                key={key}
                dayKey={key}
                todayKey={todayKey}
                events={byDay.get(key) ?? []}
                tasks={tasksByDay.get(key) ?? []}
                onEvent={(event) => setEditing({ kind: 'event', event, key: Date.now() })}
                onTask={(task) => setEditing({ kind: 'task', task, key: Date.now() })}
              />
            ))}
        </>
      )}

      {tab === 'tasks' && (
        <>
          {todo.isPending && <SkeletonList />}
          {todo.isError && <ErrorState error={todo.error} onRetry={() => void todo.refetch()} />}
          {todo.isSuccess && groups.overdue.length + groups.today.length + groups.upcoming.length + groups.none.length === 0 && (
            <EmptyState icon={ListTodo} text='Chưa có việc nào. Nhắn trợ lý như "nhắc gửi báo giá thứ Sáu", hoặc bấm dấu cộng.' />
          )}
          {(
            [
              ['QUÁ HẠN', groups.overdue],
              ['HÔM NAY', groups.today],
              ['SẮP TỚI', groups.upcoming],
              ['KHÔNG HẠN', groups.none],
              ['ĐÃ XONG', groups.done],
            ] as const
          ).map(([label, list]) =>
            list.length === 0 ? null : (
              <section key={label}>
                <h2 className={cn('text-xs font-semibold tracking-wide text-muted-foreground', label === 'QUÁ HẠN' && 'text-destructive')}>
                  {label} ({list.length})
                </h2>
                <div className="divide-y">
                  {list.map((task) => (
                    <TaskRow key={task.id} task={task} todayKey={todayKey} onClick={() => setEditing({ kind: 'task', task, key: Date.now() })} />
                  ))}
                </div>
              </section>
            ),
          )}
        </>
      )}

      <Button
        size="icon"
        aria-label="Thêm"
        className="fixed right-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-30 size-14 rounded-full shadow-lg"
        onClick={() => (tab === 'tasks' ? setEditing({ kind: 'task', task: null, key: Date.now() }) : setAddOpen(true))}
      >
        <Plus className="size-6" />
      </Button>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="top-auto bottom-[calc(4.5rem+env(safe-area-inset-bottom))] translate-y-0">
          <DialogHeader>
            <DialogTitle>Thêm</DialogTitle>
            <DialogDescription>Hoặc nhắn trợ lý: nhắc 15:00 gọi khách.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="secondary"
              className="h-16"
              onClick={() => {
                setAddOpen(false)
                setEditing({ kind: 'event', event: null, key: Date.now() })
              }}
            >
              <CalendarDays className="size-5" />
              Sự kiện
            </Button>
            <Button
              variant="secondary"
              className="h-16"
              onClick={() => {
                setAddOpen(false)
                setEditing({ kind: 'task', task: null, key: Date.now() })
              }}
            >
              <ListTodo className="size-5" />
              Việc
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {editing?.kind === 'event' && <EventDialog key={editing.key} event={editing.event} dayKey={dayKey} open onOpenChange={(open) => !open && closeEditing()} />}
      {editing?.kind === 'task' && <TaskDialog key={editing.key} task={editing.task} dayKey={dayKey} open onOpenChange={(open) => !open && closeEditing()} />}
    </div>
  )
}

function shiftMonth(key: string, months: number): string {
  const [y, m] = key.split('-').map(Number)
  const date = new Date(Date.UTC(y, m - 1 + months, 1))
  return date.toISOString().slice(0, 10)
}

interface DaySectionProps {
  dayKey: string
  todayKey: string
  events: CalendarEvent[]
  tasks: Task[]
  onEvent: (event: CalendarEvent) => void
  onTask: (task: Task) => void
  showEmpty?: boolean
}

function DaySection({ dayKey, todayKey, events, tasks, onEvent, onTask, showEmpty }: DaySectionProps) {
  const title = `${formatDayTitle(dayKey)}${dayKey === todayKey ? ' · Hôm nay' : ''}`
  if (!showEmpty && events.length === 0 && tasks.length === 0) {
    return <p className="text-xs text-muted-foreground">{title.toUpperCase()} · trống</p>
  }
  return (
    <section className="flex flex-col gap-1">
      <h2 className={cn('text-xs font-semibold tracking-wide text-muted-foreground', dayKey === todayKey && 'text-primary')}>{title.toUpperCase()}</h2>
      {events.length === 0 && tasks.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">Ngày trống.</p>}
      <div className="divide-y">
        {events.map((event) => (
          <EventRow key={`${event.id}-${event.occurrence_start ?? ''}`} event={event} dayKey={dayKey} onClick={() => onEvent(event)} />
        ))}
      </div>
      {tasks.length > 0 && (
        <>
          <h3 className="pt-2 text-xs font-semibold tracking-wide text-muted-foreground">{dayKey === todayKey ? 'VIỆC HẠN HÔM NAY' : 'VIỆC HẠN NGÀY NÀY'}</h3>
          <div className="divide-y">
            {tasks.map((task) => (
              <TaskRow key={task.id} task={task} todayKey={todayKey} onClick={() => onTask(task)} />
            ))}
          </div>
        </>
      )}
    </section>
  )
}

interface MonthGridProps {
  dayKey: string
  todayKey: string
  byDay: Map<string, CalendarEvent[]>
  tasksByDay: Map<string, Task[]>
  onPick: (key: string) => void
  onMove: (months: number) => void
}

function MonthGrid({ dayKey, todayKey, byDay, tasksByDay, onPick, onMove }: MonthGridProps) {
  const month = dayKey.slice(0, 7)
  return (
    <section className="rounded-2xl border bg-card p-2">
      <div className="flex items-center justify-between px-1 pb-2">
        <Button size="icon" variant="ghost" aria-label="Tháng trước" onClick={() => onMove(-1)}>
          <ChevronLeft className="size-4" />
        </Button>
        <span className="font-semibold">
          Tháng {Number(month.slice(5))}/{month.slice(0, 4)}
        </span>
        <Button size="icon" variant="ghost" aria-label="Tháng sau" onClick={() => onMove(1)}>
          <ChevronRight className="size-4" />
        </Button>
      </div>
      <div className="grid grid-cols-7 text-center text-[11px] text-muted-foreground">
        {WEEKDAY_SHORT.map((d) => (
          <span key={d} className="pb-1">
            {d}
          </span>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {monthGridKeys(dayKey).map((key) => {
          const count = (byDay.get(key)?.length ?? 0) + (tasksByDay.get(key)?.length ?? 0)
          return (
            <button key={key} type="button" onClick={() => onPick(key)} className={cn('flex h-12 flex-col items-center gap-1 rounded-lg pt-1', key.slice(0, 7) !== month && 'opacity-40')}>
              <span className={cn('flex size-7 items-center justify-center rounded-full text-sm tabular-nums', key === todayKey && 'bg-primary font-semibold text-primary-foreground')}>{Number(key.slice(8))}</span>
              <span className="flex gap-0.5">
                {Array.from({ length: Math.min(3, count) }, (_, i) => (
                  <span key={i} className="size-1 rounded-full bg-primary" />
                ))}
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
