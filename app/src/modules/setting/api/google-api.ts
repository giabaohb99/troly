import { apiGet, apiPost, toQuery } from '@/core/api/http-client'
import type { GooglePackName } from '@/shared/hooks/use-google-status'

// Kết nối Google (12 mục 5.6, 40 mục 3.2): máy chủ trả auth_url, app mở bằng Custom Tab.

export interface OutboxItem {
  id: number
  service: string
  op: string
  local_type: 'event' | 'task' | 'gmail_draft' | 'file' | 'export'
  local_id: number
  status: 'pending' | 'processing' | 'done' | 'failed' | 'conflict'
  attempts: number
  last_error: string | null
  has_discarded_change: boolean
  updated_at: string
}

export const connectGoogle = (packs: GooglePackName[]) => apiPost<{ auth_url: string }>('/google/connect', { packs })
export const disconnectGoogle = (keepData: boolean) => apiPost<null>('/google/disconnect', { keep_data: keepData })
export const syncGoogle = (service: string) => apiPost<{ queued: boolean }>(`/google/sync/${service}`)
export const listOutbox = () => apiGet<{ items: OutboxItem[] }>(`/google/outbox${toQuery({ status: 'failed,conflict' })}`)
export const retryOutbox = (id: number, reapply: boolean) => apiPost<OutboxItem>(`/google/outbox/${id}/retry`, { reapply })
