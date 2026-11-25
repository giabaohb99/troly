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
  // Trợ lý xin nối một hệ thống (QĐ-56).
  | (ActionBase & { type: 'connect'; connector_id?: number | null; name?: string | null; url?: string | null })

export const KNOWN_ACTION_TYPES = new Set(['open_map_navigation', 'open_map_directions', 'open_map_place', 'open_link', 'open_screen', 'confirm', 'undo', 'memory_changed', 'choices', 'file', 'connect'])

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

// Phiên chat đặt tên (QĐ-51 bước 1), dạng đã chốt với agent kiến trúc (25/11). Tên tự đặt chạy nền sau câu trả lời
// đầu (title_source auto); last_preview là 120 ký tự đầu tin cuối, chưa có thì app dùng summary.
export interface ChatSession {
  id: number
  title?: string | null
  title_source?: 'auto' | 'user' | null
  pinned?: boolean
  started_at?: string | null
  last_message_at?: string | null
  last_preview?: string | null
  summary?: string | null
  message_count?: number
  created_at?: string | null
  local_date?: string | null
}

// Một phiên mở trên màn chat: /chat/today (phiên hoạt động gần nhất) hoặc GET /chat/conversations/{id}.
export interface ChatToday {
  conversation: ChatSession | null
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
