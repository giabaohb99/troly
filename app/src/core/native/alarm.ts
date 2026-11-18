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

// Cài đặt thông báo lưu trên máy (QĐ-38). quietStart, quietEnd dạng HH:MM; null là tắt giờ yên lặng.
export interface NotifyPrefs {
  sound: boolean
  quietStart: string | null
  quietEnd: string | null
  // Báo khi trợ lý trả lời lúc app không ở màn hình (QĐ-41).
  chatDone: boolean
}

// Kênh thông báo Android, mỗi loại một kênh để chỉnh âm thanh, rung trong cài đặt máy.
export const NOTIFY_CHANNELS = [
  { id: 'nhac-lich', label: 'Nhắc lịch' },
  { id: 'bao-thuc', label: 'Báo thức (khi bảo trợ lý đặt báo thức)' },
  { id: 'giao-dich', label: 'Giao dịch mới' },
  { id: 'tin-quan-trong', label: 'Tin quan trọng' },
  { id: 'tro-ly-tra-loi', label: 'Trợ lý trả lời' },
  { id: 'cap-nhat', label: 'Cập nhật app' },
  { id: 'he-thong', label: 'Hệ thống' },
] as const

export interface AlarmPlugin {
  sync(): Promise<{ outcome?: 'ok' | 'retry' | 'revoked' }>
  getNotifyPrefs(): Promise<NotifyPrefs>
  setNotifyPrefs(options: Partial<NotifyPrefs>): Promise<void>
  openChannelSettings(options: { channel: string }): Promise<{ opened: boolean }>
  notifyChatDone(options: { messageId: string; deepLink: string; body: string | null; fileLink: string | null }): Promise<void>
  startNoticeBurst(): Promise<void>
  getScheduled(): Promise<AlarmStatus>
  canScheduleExact(): Promise<{ value: boolean }>
  addListener(event: 'reminderAction', listener: (event: ReminderActionEvent) => void): Promise<PluginListenerHandle>
}

const WEB_PREFS_KEY = 'troly.notify.prefs'

class AlarmWeb extends WebPlugin {
  async sync() {
    return { outcome: 'ok' as const }
  }

  async getNotifyPrefs(): Promise<NotifyPrefs> {
    const saved = localStorage.getItem(WEB_PREFS_KEY)
    return { sound: true, quietStart: null, quietEnd: null, chatDone: true, ...(saved ? (JSON.parse(saved) as Partial<NotifyPrefs>) : {}) }
  }

  async setNotifyPrefs(options: Partial<NotifyPrefs>) {
    localStorage.setItem(WEB_PREFS_KEY, JSON.stringify({ ...(await this.getNotifyPrefs()), ...options }))
  }

  async openChannelSettings() {
    return { opened: false }
  }

  async notifyChatDone() {}

  async startNoticeBurst() {}

  async getScheduled(): Promise<AlarmStatus> {
    return { count: 0, revision: null, lastSyncAt: null, exactAllowed: true, next: [] }
  }

  async canScheduleExact() {
    return { value: true }
  }
}

export const Alarm = registerPlugin<AlarmPlugin>('Alarm', { web: () => new AlarmWeb() })
