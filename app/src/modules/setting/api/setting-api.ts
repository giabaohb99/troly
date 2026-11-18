import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from '@/core/api/http-client'

export interface Profile {
  content: string
  version: number
  updated_by: string | null
  updated_at: string | null
}

export interface DeviceRow {
  id: number
  name: string
  model: string | null
  app_version_name: string | null
  last_seen_at: string | null
}

export interface CostStatus {
  today_usd: number
  month_usd: number
  monthly_warn_usd: number
  over_monthly_warning: boolean
}

export const getProfile = () => apiGet<Profile>('/memory/profile')
export const saveProfile = (content: string, version: number) => apiPut<Profile>('/memory/profile', { content, version })
export const listDevices = () => apiGet<{ items: DeviceRow[] }>('/devices')
export const revokeDevice = (id: number) => apiDelete<null>(`/devices/${id}`)
export const getCostStatus = () => apiGet<CostStatus>('/chat/status')

export interface ProfileRevision {
  version: number
  changed_by: string | null
  reason: string | null
  created_at: string
  preview: string | null
}

export const listProfileRevisions = () => apiGet<{ items: ProfileRevision[]; next_cursor: string | null }>('/memory/profile/revisions')
// Khôi phục bản cũ: gửi phiên bản hiện tại để máy chủ kiểm lệch (12 dòng /memory/profile/revisions/{version}/restore).
export const restoreProfileRevision = (version: number, currentVersion: number) => apiPost<Profile>(`/memory/profile/revisions/${version}/restore`, { version: currentVersion })
export const renameDevice = (id: number, name: string) => apiPatch<DeviceRow>(`/devices/${id}`, { name })

// Cài đặt dạng khóa, giá trị (12 dòng /settings; khóa ở backend/app/modules/setting/service.py).
export interface Ferry {
  name: string
  place_query: string | null
  first_time: string | null
  last_time: string | null
  hotline: string | null
  note: string | null
  // YYYY-MM-DD; tối đa 10 tuyến.
  updated_at: string | null
}

export interface SettingValues {
  'inbox.ai_enabled': boolean
  'calendar.default_remind_minutes': number[]
  'trip.default_travel_mode': 'motorbike' | 'car' | 'walk'
  'trip.night_start': string
  'trip.night_end': string
  'trip.ride_break_minutes': number
  'trip.speed_factor': number
  'trip.ferries'?: Ferry[]
  // QĐ-38: máy chủ lọc /device/notices và /calendar/reminders theo các khóa này.
  'notify.new_transaction'?: boolean
  'notify.important_message'?: boolean
  'calendar.app_reminds_google'?: boolean
  // QĐ-41: notice chat_done khi trợ lý trả lời lúc app chạy nền.
  'notify.chat_done'?: boolean
  [key: string]: unknown
}

export const getSettings = () => apiGet<{ values: SettingValues; defaults: SettingValues }>('/settings')
export const patchSettings = (values: Partial<SettingValues>) => apiPatch<{ values: SettingValues }>('/settings', values)

// Luật hộp tin: người quan trọng, từ khóa gấp (12 mục 5.4).
export interface InboxRule {
  id: number
  kind: 'vip_sender' | 'urgent_keyword' | 'muted_sender' | 'private_conversation'
  value: string
  app: string | null
  created_at: string
}

export const listInboxRules = () => apiGet<{ items: InboxRule[] }>('/inbox/rules')
export const createInboxRule = (kind: InboxRule['kind'], value: string) => apiPost<InboxRule>('/inbox/rules', { kind, value, app: null })
export const deleteInboxRule = (id: number) => apiDelete<null>(`/inbox/rules/${id}`)
