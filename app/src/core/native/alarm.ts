import { registerPlugin, WebPlugin, type PluginListenerHandle } from '@capacitor/core'

// Nhắc lịch trên máy (30 mục 3.4, 3.9). Trên Android: AlarmPlugin.kt. Lớp gốc tự tải /calendar/reminders bằng
// mã thiết bị (WorkManager mỗi giờ) và đặt AlarmManager; giao diện chỉ gọi sync() sau khi sửa lịch hoặc việc.

export interface ScheduledReminder {
  key: string
  title: string
  fireAt: number
  kind: 'normal' | 'alarm'
}

export interface AlarmStatus {
  count: number
  revision: string | null
  lastSyncAt: number | null
  exactAllowed: boolean
  next: ScheduledReminder[]
}

export interface ReminderActionEvent {
  key: string
  source: 'event' | 'task'
  sourceId: string | null
  action: 'done' | 'ack' | 'snooze'
}

export interface AlarmPlugin {
  sync(): Promise<void>
  getScheduled(): Promise<AlarmStatus>
  canScheduleExact(): Promise<{ value: boolean }>
  addListener(event: 'reminderAction', listener: (event: ReminderActionEvent) => void): Promise<PluginListenerHandle>
}

class AlarmWeb extends WebPlugin {
  async sync() {}

  async getScheduled(): Promise<AlarmStatus> {
    return { count: 0, revision: null, lastSyncAt: null, exactAllowed: true, next: [] }
  }

  async canScheduleExact() {
    return { value: true }
  }
}

export const Alarm = registerPlugin<AlarmPlugin>('Alarm', { web: () => new AlarmWeb() })
