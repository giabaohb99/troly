import { apiDelete, apiGet, apiPut } from '@/core/api/http-client'

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
