import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/core/api/http-client'
import { queryKeys } from '@/shared/constants/query-keys'

// Trạng thái kết nối Google (12 mục 5.6). Dùng ở màn Lịch (dòng đồng bộ, dải mời kết nối) và màn Kết nối Google.

export type GooglePackName = 'base' | 'calendar' | 'tasks' | 'gmail' | 'contacts' | 'drive'

export interface GooglePack {
  name: GooglePackName
  enabled: boolean
  granted: boolean
  last_sync_at: string | null
  status: 'ok' | 'error' | 'disabled' | null
  last_error: string | null
}

export interface GoogleStatus {
  connected: boolean
  email: string | null
  // Trạng thái tài khoản: active, reauth_required, revoked.
  status: 'active' | 'reauth_required' | 'revoked' | null
  // Gói `base` không có trong danh sách.
  packs: GooglePack[]
  initial_sync: { state: 'pending' | 'running' | 'done' | 'failed' | null; message: string }
  failed_outbox_count: number
}

export const getGoogleStatus = () => apiGet<GoogleStatus>('/google/status')

export function useGoogleStatus() {
  return useQuery({ queryKey: queryKeys.google.status, queryFn: getGoogleStatus, staleTime: 60_000 })
}

// Tài khoản đã nối nhưng token hỏng hoặc bị thu hồi: cần nối lại.
export function needsReconnect(status: GoogleStatus | undefined): boolean {
  return status?.status === 'reauth_required'
}
