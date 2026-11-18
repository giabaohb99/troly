import { apiDelete, apiGet, apiPatch, apiPost, toQuery } from '@/core/api/http-client'
import type { CalendarEvent, EventInput, EventPendingAction, SaveEventResult, Task, TaskInput } from '@/modules/calendar/types/calendar'
import { toConfirmInfo, type ConfirmInfo } from '@/shared/types/pending-action'

// Sự kiện: GET trả lần lặp đã trải; sửa, xóa một lần lặp thì gửi kèm occurrence_start (12 mục 5.5).
export const listEvents = (from: string, to: string) => apiGet<{ items: CalendarEvent[] }>(`/calendar/events${toQuery({ from, to })}`)
export const getEvent = (id: number, occurrenceStart?: string | null) =>
  apiGet<CalendarEvent>(`/calendar/events/${id}${toQuery({ occurrence_start: occurrenceStart })}`)
export const createEvent = (input: EventInput) => apiPost<SaveEventResult>('/calendar/events', input)
export const updateEvent = (id: number, input: Partial<EventInput>, occurrenceStart: string | null) =>
  apiPatch<SaveEventResult>(`/calendar/events/${id}${toQuery({ occurrence_start: occurrenceStart })}`, input)
export const deleteEvent = (id: number, occurrenceStart: string | null) =>
  apiDelete<{ pending_action: EventPendingAction } | null>(`/calendar/events/${id}${toQuery({ occurrence_start: occurrenceStart })}`)
export const restoreEvent = (id: number) => apiPost<CalendarEvent>(`/calendar/events/${id}/restore`)

// Việc (12 mục 5.5).
export const listTasks = (status: 'todo' | 'done', limit: number) => apiGet<{ items: Task[]; next_cursor: string | null }>(`/tasks${toQuery({ status, limit })}`)
export const getTask = (id: number) => apiGet<Task>(`/tasks/${id}`)
export const createTask = (input: TaskInput) => apiPost<Task>('/tasks', input)
export const updateTask = (id: number, input: Partial<TaskInput>) => apiPatch<Task>(`/tasks/${id}`, input)
export const deleteTask = (id: number) => apiDelete<null>(`/tasks/${id}`)
export const restoreTask = (id: number) => apiPost<Task>(`/tasks/${id}/restore`)
export const completeTask = (id: number) => apiPost<Task>(`/tasks/${id}/complete`)
export const reopenTask = (id: number) => apiPost<Task>(`/tasks/${id}/reopen`)
export const resolveRemoteDelete = (id: number, keep: boolean) => apiPost<Task | null>(`/tasks/${id}/resolve-remote-delete`, { keep })

export function isPending(result: unknown): result is { pending_action: EventPendingAction } {
  return typeof result === 'object' && result !== null && 'pending_action' in result
}

// Ưu tiên thẻ `confirm` máy chủ dựng sẵn; thiếu thì dựng từ PendingAction với nhãn nút của app.
export function confirmOf(pending: EventPendingAction, fallbackLabel: string): ConfirmInfo {
  const built = pending.action
  if (built?.pending_action_id) return { ...built, confirm_label: built.confirm_label || fallbackLabel }
  return toConfirmInfo(pending, { confirm: fallbackLabel })
}
