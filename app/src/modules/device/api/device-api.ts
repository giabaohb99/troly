import { apiGet, apiPatch } from '@/core/api/http-client'

// Danh sách app được nghe (tab_listened_app, máy chủ là gốc; chỉ đổi ở màn này, không qua trợ lý).
export interface ListenedAppRow {
  id: number
  package_name: string
  label: string
  purpose: 'expense' | 'inbox'
  parser: string
  enabled: boolean
  is_default: boolean
}

export const listListenedApps = () => apiGet<{ items: ListenedAppRow[] }>('/devices/listened-apps')
export const setListenedAppEnabled = (id: number, enabled: boolean) => apiPatch<ListenedAppRow>(`/devices/listened-apps/${id}`, { enabled })

export const SMS_DEFAULT = 'sms_default'
export const SMS_PACKAGES = ['com.samsung.android.messaging', 'com.google.android.apps.messaging']
