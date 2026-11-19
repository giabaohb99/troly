import { registerPlugin, WebPlugin } from '@capacitor/core'

// Trạng thái plugin nghe thông báo (30 mục 3.4). Trên Android: NotifyPlugin.kt; trên trình duyệt: bản giả.

export interface NotifyStatus {
  listenerGranted: boolean
  listenerConnected: boolean
  lastEventAt: number | null
  queueSize: number
  droppedToday: number
  otpBlockedToday: number
  otpRejectedByServer: number
  deviceRegistered: boolean
  deviceRevoked: boolean
  configRevision: string | null
}

export interface NotifyPlugin {
  getStatus(): Promise<NotifyStatus>
  flushQueue(): Promise<void>
  sync(): Promise<void>
  // Mở cuộc chat gốc (QĐ-43): thông báo gốc còn thì mở đúng cuộc chat, không thì mở app.
  openSource(options: { packageName: string; titles: string[] }): Promise<{ opened: 'notification' | 'app' | null }>
}

class NotifyWeb extends WebPlugin implements NotifyPlugin {
  async getStatus(): Promise<NotifyStatus> {
    return {
      listenerGranted: false,
      listenerConnected: false,
      lastEventAt: null,
      queueSize: 0,
      droppedToday: 0,
      otpBlockedToday: 0,
      otpRejectedByServer: 0,
      deviceRegistered: false,
      deviceRevoked: false,
      configRevision: null,
    }
  }

  async flushQueue() {}

  async sync() {}

  async openSource() {
    return { opened: null }
  }
}

export const Notify = registerPlugin<NotifyPlugin>('Notify', { web: () => new NotifyWeb() })
