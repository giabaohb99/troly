import { registerPlugin, WebPlugin, type PluginListenerHandle } from '@capacitor/core'

// Quyền và trang cài đặt hệ thống cho màn Thiết lập máy (30 mục 3.10). Trên Android: SystemPlugin.kt.
// Trên trình duyệt: bản giả, coi như máy Samsung chưa cấp gì để làm giao diện.

export interface PermissionSnapshot {
  notifications: boolean
  notificationListener: boolean
  batteryUnrestricted: boolean
  exactAlarm: boolean
  installPackages: boolean
  defaultSmsPackage: string | null
  defaultSmsLabel: string | null
  manufacturer: string
  model: string
  androidSdk: number
}

export type SettingsTarget =
  | 'notification_listener'
  | 'app_details'
  | 'battery'
  | 'samsung_never_sleeping'
  | 'exact_alarm'
  | 'unknown_sources'
  | 'notifications'
  | 'default_apps'

export interface SystemPlugin {
  getPermissions(): Promise<PermissionSnapshot>
  requestNotifications(): Promise<PermissionSnapshot>
  openSettings(options: { target: SettingsTarget }): Promise<{ opened: boolean }>
  getInstalledApps(options: { packages: string[] }): Promise<{ installed: string[] }>
  addListener(event: 'permissionsChanged', listener: (snapshot: PermissionSnapshot) => void): Promise<PluginListenerHandle>
  // Giao diện sáng, tối (QĐ-37): màu chữ và nền của thanh trạng thái, thanh điều hướng; chế độ tối của máy.
  setBarStyle(options: { dark: boolean; color: string }): Promise<void>
  getSystemTheme(): Promise<{ dark: boolean }>
  addListener(event: 'systemThemeChanged', listener: (state: { dark: boolean }) => void): Promise<PluginListenerHandle>
}

class SystemWeb extends WebPlugin {
  private state: PermissionSnapshot = {
    notifications: false,
    notificationListener: false,
    batteryUnrestricted: false,
    exactAlarm: true,
    installPackages: false,
    defaultSmsPackage: 'com.samsung.android.messaging',
    defaultSmsLabel: 'Tin nhắn',
    manufacturer: 'samsung',
    model: 'SM-S936B (giả)',
    androidSdk: 35,
  }

  async getPermissions() {
    return { ...this.state }
  }

  async requestNotifications() {
    this.state.notifications = true
    return { ...this.state }
  }

  // Bản giả: "mở" trang thì coi như người dùng đã bật, để thử luồng trên trình duyệt.
  async openSettings({ target }: { target: SettingsTarget }) {
    if (target === 'notification_listener') this.state.notificationListener = true
    if (target === 'battery') this.state.batteryUnrestricted = true
    if (target === 'notifications') this.state.notifications = true
    this.notifyListeners('permissionsChanged', { ...this.state })
    return { opened: target !== 'samsung_never_sleeping' }
  }

  async getInstalledApps({ packages }: { packages: string[] }) {
    return { installed: packages.filter((p) => p !== 'com.google.android.apps.messaging') }
  }

  async setBarStyle() {}

  async getSystemTheme() {
    return { dark: window.matchMedia('(prefers-color-scheme: dark)').matches }
  }
}

export const System = registerPlugin<SystemPlugin>('System', { web: () => new SystemWeb() })
