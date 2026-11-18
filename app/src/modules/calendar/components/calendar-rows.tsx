import { AlarmClock, Bell, Check, Flag, MapPin, Repeat, TriangleAlert, Users } from 'lucide-react'
import { useResolveRemoteDelete, useToggleTask } from '@/modules/calendar/hooks/use-calendar'
import type { CalendarEvent, Task } from '@/modules/calendar/types/calendar'
import { remindLabel, taskDueKey } from '@/modules/calendar/utils/calendar-dates'
import { Button } from '@/shared/ui/button'
import { formatDayTitle, formatTime, toDateKey } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

function eventTime(event: CalendarEvent, dayKey: string): string {
  if (event.all_day || !event.start_at) return 'Cả ngày'
  // Sự kiện bắt đầu từ hôm trước: hiện "tới HH:MM".
  if (toDateKey(event.start_at) < dayKey) return event.end_at ? `tới ${formatTime(event.end_at)}` : 'Cả ngày'
  return formatTime(event.start_at)
}

// Một dòng sự kiện: giờ, tiêu đề, nguồn nhắc (App kèm số phút, Báo thức, Google), địa điểm, số khách.
export function EventRow({ event, dayKey, onClick }: { event: CalendarEvent; dayKey: string; onClick: () => void }) {
  const remind = remindLabel(event)
  const guests = event.attendees.filter((a) => !a.is_self).length
  return (
    <button type="button" onClick={onClick} className="flex w-full gap-3 py-2.5 text-left">
      <span className="w-12 shrink-0 pt-0.5 text-sm text-muted-foreground tabular-nums">{eventTime(event, dayKey)}</span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className={cn('truncate font-medium', event.status === 'tentative' && 'italic')}>{event.title}</span>
          {event.is_recurring && <Repeat className="size-3.5 shrink-0 text-muted-foreground" aria-label="Lặp" />}
        </span>
        {(event.location || guests > 0) && (
          <span className="flex items-center gap-2 truncate text-xs text-muted-foreground">
            {event.location && (
              <span className="flex min-w-0 items-center gap-1 truncate">
                <MapPin className="size-3 shrink-0" />
                {event.location}
              </span>
            )}
            {guests > 0 && (
              <span className="flex shrink-0 items-center gap-1">
                <Users className="size-3" />
                {guests} khách
              </span>
            )}
          </span>
        )}
      </span>
      {remind && (
        <span className={cn('flex shrink-0 items-center gap-1 pt-0.5 text-xs', event.remind_source === 'app' ? 'text-primary' : 'text-muted-foreground')}>
          {event.is_alarm ? <AlarmClock className="size-3.5" /> : <Bell className="size-3.5" />}
          {remind}
        </span>
      )}
    </button>
  )
}

const PRIORITY_LABEL = { high: 'cao', low: 'thấp', normal: null } as const

function dueText(task: Task, todayKey: string): string | null {
  const key = taskDueKey(task)
  if (!key) return null
  const time = task.due_at ? formatTime(task.due_at) : null
  if (key === todayKey) return time ? `Hôm nay ${time}` : 'Hôm nay'
  return [formatDayTitle(key), time].filter(Boolean).join(' ')
}

// Một dòng việc: ô tích làm ngay, nhãn hạn, ưu tiên; việc bị xóa trên Google Tasks có hai nút chọn (QĐ-21).
export function TaskRow({ task, todayKey, onClick }: { task: Task; todayKey: string; onClick: () => void }) {
  const toggle = useToggleTask()
  const resolve = useResolveRemoteDelete()
  const done = task.status === 'done'
  const due = dueText(task, todayKey)
  const overdue = !done && (taskDueKey(task) ?? '9') < todayKey
  const priority = PRIORITY_LABEL[task.priority]
  return (
    <div className="py-2.5">
      <div className="flex items-start gap-3">
        <button
          type="button"
          role="checkbox"
          aria-checked={done}
          aria-label={done ? `Bỏ xong ${task.title}` : `Xong ${task.title}`}
          disabled={toggle.isPending}
          onClick={() => toggle.mutate(task)}
          className={cn('mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md border', done && 'border-primary bg-primary text-primary-foreground')}
        >
          {done && <Check className="size-3.5" />}
        </button>
        <button type="button" onClick={onClick} className="min-w-0 flex-1 text-left">
          <span className={cn('block truncate', done && 'text-muted-foreground line-through')}>{task.title}</span>
          {(due || task.completed_source === 'google') && (
            <span className={cn('block text-xs text-muted-foreground', overdue && 'text-destructive')}>
              {done && task.completed_source === 'google' ? 'Xong trên Google Tasks' : due}
            </span>
          )}
        </button>
        {priority && (
          <span className={cn('flex shrink-0 items-center gap-1 text-xs', task.priority === 'high' ? 'text-warning' : 'text-muted-foreground')}>
            <Flag className="size-3.5" />
            {priority}
          </span>
        )}
      </div>
      {task.sync_status === 'remote_deleted' && (
        <div className="mt-2 ml-8 flex flex-wrap items-center gap-2 rounded-xl bg-warning/10 px-3 py-2 text-xs text-warning">
          <TriangleAlert className="size-3.5" />
          <span className="flex-1">Đã xóa trên Google Tasks</span>
          <Button size="sm" variant="outline" disabled={resolve.isPending} onClick={() => resolve.mutate({ id: task.id, keep: false })}>
            Xóa luôn
          </Button>
          <Button size="sm" variant="secondary" disabled={resolve.isPending} onClick={() => resolve.mutate({ id: task.id, keep: true })}>
            Giữ lại
          </Button>
        </div>
      )}
    </div>
  )
}
