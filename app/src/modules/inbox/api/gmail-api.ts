import { apiGet, apiPost } from '@/core/api/http-client'
import type { PendingAction } from '@/shared/types/pending-action'

// Gmail (QĐ-43): đọc luồng thư, soạn nháp, gửi qua thẻ duyệt (12, dòng /gmail; dạng chi tiết đã đề nghị agent
// Google ở mục 5 bảng việc). Chưa cấp gói gmail thì máy chủ trả 409 GOOGLE_NOT_CONNECTED.

export interface GmailMessage {
  id: string
  from_name: string | null
  from_email: string
  to: string[]
  cc: string[]
  date: string
  text: string
}

export interface GmailThread {
  thread_id: string
  subject: string
  messages: GmailMessage[]
  reply: { to: string[]; cc: string[]; subject: string; in_reply_to: string | null } | null
}

export interface DraftInput {
  to: string[]
  cc: string[]
  subject: string
  body: string
  thread_ref: string | null
}

export interface GmailDraft extends DraftInput {
  id: number
  status: string
}

export const GMAIL_KEY_PREFIX = 'gmail:'
export const threadIdFromKey = (key: string) => (key.startsWith(GMAIL_KEY_PREFIX) ? key.slice(GMAIL_KEY_PREFIX.length) : key)

export const getThread = (threadId: string) => apiGet<GmailThread>(`/gmail/threads/${encodeURIComponent(threadId)}`)
export const createDraft = (input: DraftInput) => apiPost<GmailDraft>('/gmail/drafts', input)
export const sendDraft = (id: number) => apiPost<{ pending_action: PendingAction & { action?: unknown } }>(`/gmail/drafts/${id}/send`)

// Danh sách email trong ô nhập: tách bằng dấu phẩy, chấm phẩy, khoảng trắng; bỏ trùng; giữ thứ tự.
export function parseEmails(text: string): { valid: string[]; invalid: string[] } {
  const parts = text.split(/[\s,;]+/).map((p) => p.trim()).filter(Boolean)
  const valid: string[] = []
  const invalid: string[] = []
  for (const part of parts) {
    const email = part.toLowerCase()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) invalid.push(part)
    else if (!valid.includes(email)) valid.push(email)
  }
  return { valid, invalid }
}
