import type { PendingAction } from '@/shared/types/pending-action'

// Kiểu theo 12-api.md mục 3.9 (hành động, vỏ phẳng) và 5.2 (chat).

export type ChatMode = 'chat' | 'think' | 'research' | 'summary'

export interface Citation {
  title: string
  url: string
}

interface ActionBase {
  id: string
  label: string
}

export type ChatAction =
  | (ActionBase & { type: 'open_map_navigation'; lat: number | null; lng: number | null; query: string | null; mode: string; avoid: string | null; uri?: string | null; fallback_url: string })
  | (ActionBase & { type: 'open_map_directions'; urls: string[]; segment_labels: string[] })
  | (ActionBase & { type: 'open_map_place'; query: string; place_id: string | null })
  | (ActionBase & { type: 'open_link'; url: string; kind: 'file' | 'gmail' | 'sheet' | 'web' })
  | (ActionBase & { type: 'open_screen'; screen: string; params: Record<string, string | number> | null })
  | (ActionBase & { type: 'confirm'; pending_action_id: number; title: string; summary: string; details: { label: string; value: string }[]; confirm_label: string; cancel_label: string; danger: boolean; expires_at: string })
  | (ActionBase & { type: 'undo'; text: string; resource: 'expense' | 'task' | 'event'; ids: number[]; expires_at: string })
  | (ActionBase & { type: 'memory_changed'; version: number; text: string; undo_version: number })
  | (ActionBase & { type: 'choices'; options: { label: string; value: string }[] })
  // Tệp bot xuất (QĐ-41, agent AI): label bằng name.
  | (ActionBase & { type: 'file'; file_id: number; name: string; mime: string; size_bytes: number | null })

export const KNOWN_ACTION_TYPES = new Set(['open_map_navigation', 'open_map_directions', 'open_map_place', 'open_link', 'open_screen', 'confirm', 'undo', 'memory_changed', 'choices', 'file'])

// Tin người dùng: máy chủ có thể chỉ gửi file_id (app hỏi thêm GET /files/{id}); tin trợ lý có đủ trường.
export interface Attachment {
  file_id: number
  mime?: string | null
  name?: string | null
  // Tệp bot xuất (QĐ-41) có cỡ; tệp người dùng gửi có thể không.
  size_bytes?: number | null
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant' | 'system'
  text: string
  model: string | null
  citations: Citation[] | null
  attachments: Attachment[] | null
  actions: ChatAction[] | null
  status: string | null
  created_at: string
}

export type { PendingAction, PendingStatus } from '@/shared/types/pending-action'

export interface ChatToday {
  conversation: { id: number; local_date: string } | null
  messages: ChatMessage[]
  next_cursor: string | null
  pending_actions: PendingAction[]
}

export interface ChatStatus {
  models: Record<string, string> | null
  today_usd: number
  month_usd: number
  monthly_warn_usd: number
  over_monthly_warning: boolean
}
