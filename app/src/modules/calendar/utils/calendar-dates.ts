import type { CalendarEvent, CalendarView, Task } from '@/modules/calendar/types/calendar'
import { toDateKey } from '@/shared/utils/format'

// Ngày trên lịch là khóa "YYYY-MM-DD" theo giờ Việt Nam (UTC+7, không đổi giờ mùa hè).

function keyToUtc(key: string): number {
  const [y, m, d] = key.split('-').map(Number)
  return Date.UTC(y, m - 1, d)
}

function utcToKey(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

export function addDays(key: string, days: number): string {
  return utcToKey(keyToUtc(key) + days * 86_400_000)
}

export function weekStartKey(key: string): string {
  const weekday = new Date(keyToUtc(key)).getUTCDay()
  return addDays(key, -((weekday + 6) % 7))
}

export function weekKeys(key: string): string[] {
  const start = weekStartKey(key)
  return Array.from({ length: 7 }, (_, i) => addDays(start, i))
}

export function monthGridKeys(key: string): string[] {
  const start = weekStartKey(`${key.slice(0, 7)}-01`)
  return Array.from({ length: 42 }, (_, i) => addDays(start, i))
}

const startOfDayIso = (key: string) => `${key}T00:00:00+07:00`

// Kiểu Ngày tải cả tuần để dải tuần có chấm; tháng tải đủ 42 ô (dưới mốc 92 ngày của API).
export function viewRange(view: CalendarView, key: string): { from: string; to: string } {
  if (view === 'month') {
    const grid = monthGridKeys(key)
    return { from: startOfDayIso(grid[0]), to: startOfDayIso(addDays(grid[41], 1)) }
  }
  const start = weekStartKey(key)
  return { from: startOfDayIso(start), to: startOfDayIso(addDays(start, 7)) }
}

const MAX_SPAN_DAYS = 62

export function eventDayKeys(event: CalendarEvent): string[] {
  let first: string
  let last: string
  if (event.all_day) {
    if (!event.start_date) return []
    first = event.start_date
    last = event.end_date && event.end_date > first ? addDays(event.end_date, -1) : first
  } else {
    if (!event.start_at) return []
    first = toDateKey(event.start_at)
    const endMs = event.end_at ? Date.parse(event.end_at) - 1 : Date.parse(event.start_at)
    last = endMs > Date.parse(event.start_at) ? toDateKey(new Date(endMs)) : first
  }
  const keys: string[] = []
  for (let key = first; key <= last && keys.length < MAX_SPAN_DAYS; key = addDays(key, 1)) keys.push(key)
  return keys
}

// Cả ngày đứng trước; còn lại so theo thời điểm thật (chuỗi ISO có thể khác múi: Z hoặc +07:00).
function sortValue(event: CalendarEvent): number {
  return event.all_day ? 0 : Date.parse(event.start_at ?? '')
}

export function eventsByDay(events: CalendarEvent[]): Map<string, CalendarEvent[]> {
  const map = new Map<string, CalendarEvent[]>()
  for (const event of events) {
    if (event.status === 'cancelled') continue
    for (const key of eventDayKeys(event)) map.set(key, [...(map.get(key) ?? []), event])
  }
  for (const list of map.values()) list.sort((a, b) => sortValue(a) - sortValue(b))
  return map
}

// Nguồn nhắc trên dòng sự kiện (31 mục 3.5): App kèm số phút, Báo thức, hoặc Google.
export function remindLabel(event: CalendarEvent): string | null {
  if (event.remind_source === 'google') return 'Google'
  if (event.remind_minutes.length === 0) return null
  if (event.is_alarm) return 'Báo thức'
  const minutes = Math.min(...event.remind_minutes)
  return minutes === 0 ? 'App đúng giờ' : `App ${minutes}'`
}

export function taskDueKey(task: Task): string | null {
  if (task.due_date) return task.due_date
  return task.due_at ? toDateKey(task.due_at) : null
}

export interface TaskGroups {
  overdue: Task[]
  today: Task[]
  upcoming: Task[]
  none: Task[]
  done: Task[]
}

export function groupTasks(tasks: Task[], todayKey: string): TaskGroups {
  const groups: TaskGroups = { overdue: [], today: [], upcoming: [], none: [], done: [] }
  for (const task of tasks) {
    if (task.status === 'done') {
      groups.done.push(task)
      continue
    }
    if (task.status !== 'todo') continue
    const key = taskDueKey(task)
    if (!key) groups.none.push(task)
    else if (key < todayKey) groups.overdue.push(task)
    else if (key === todayKey) groups.today.push(task)
    else groups.upcoming.push(task)
  }
  // Việc chỉ có ngày xếp sau việc có giờ của cùng ngày.
  const dueValue = (task: Task) => (task.due_at ? Date.parse(task.due_at) : Date.parse(`${task.due_date}T23:59:59+07:00`))
  const byDue = (a: Task, b: Task) => dueValue(a) - dueValue(b)
  groups.overdue.sort(byDue)
  groups.upcoming.sort(byDue)
  return groups
}

// Ô datetime-local theo giờ Việt Nam và ngược lại.
export function toLocalInput(iso: string): string {
  const ms = Date.parse(iso) + 7 * 3_600_000
  return new Date(ms).toISOString().slice(0, 16)
}

export function fromLocalInput(value: string): string {
  return `${value}:00+07:00`
}
