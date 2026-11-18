import type { ConfirmInfo, PendingAction } from '@/shared/types/pending-action'

// Kiểu theo 12-api.md mục 5.5.

export interface Attendee {
  email: string
  name: string | null
  response_status: string | null
  is_self: boolean
}

export type RemindSource = 'app' | 'google'

export interface CalendarEvent {
  id: number
  occurrence_start: string | null
  is_recurring: boolean
  title: string
  description: string | null
  location: string | null
  all_day: boolean
  start_at: string | null
  end_at: string | null
  start_date: string | null
  end_date: string | null
  status: 'confirmed' | 'tentative' | 'cancelled'
  remind_minutes: number[]
  remind_source: RemindSource
  is_alarm: boolean
  attendees: Attendee[]
  source: 'app' | 'google'
  task_id: number | null
  sync_status: string
  google_html_link: string | null
  // Đề xuất ở mục 5 bảng việc: false khi là sự kiện người khác mời (chỉ đổi được Ai nhắc). Thiếu thì coi là true.
  is_organizer?: boolean
}

export interface EventInput {
  title: string
  description: string | null
  location: string | null
  all_day: boolean
  start_at?: string | null
  end_at?: string | null
  start_date?: string | null
  end_date?: string | null
  remind_minutes: number[]
  remind_source: RemindSource
  is_alarm: boolean
  attendees: string[]
}

export type TaskStatus = 'todo' | 'done' | 'cancelled'
export type TaskPriority = 'low' | 'normal' | 'high'

export interface Task {
  id: number
  title: string
  note: string | null
  status: TaskStatus
  priority: TaskPriority
  due_date: string | null
  due_at: string | null
  completed_at: string | null
  completed_source: 'app' | 'google' | null
  event_id: number | null
  sync_status: string
}

export interface TaskInput {
  title: string
  note: string | null
  priority: TaskPriority
  due_date: string | null
  due_at: string | null
}

// Lưu sự kiện có khách thì máy chủ trả 202 với việc chờ duyệt (QĐ-23); `action` là thẻ `confirm` máy chủ dựng sẵn.
export type EventPendingAction = PendingAction & { action?: ConfirmInfo | null }
export type SaveEventResult = CalendarEvent | { pending_action: EventPendingAction }

export type CalendarView = 'day' | 'week' | 'month'
