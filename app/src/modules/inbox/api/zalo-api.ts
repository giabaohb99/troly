import { apiGet, apiPost } from '@/core/api/http-client'

// Zalo đầy đủ qua zalo-bridge (QĐ-52): danh bạ để mở hội thoại mới, lấy tin cũ, gửi tin. Tin đọc ở /inbox như cũ.

export interface ZaloContact {
  thread_id: string
  thread_type: 'user' | 'group'
  name: string
  avatar: string | null
  conversation_key: string
}

export interface SendZaloInput {
  conversation_key: string
  text?: string
  file_ids?: number[]
  client_ref?: string
}

export const listZaloContacts = () => apiGet<{ items: ZaloContact[] }>('/zalo/contacts')
export const syncZaloConversation = (key: string) => apiPost<{ mode: 'group_history' | 'requested'; saved?: number }>(`/zalo/conversations/${encodeURIComponent(key)}/sync`)
export const sendZaloMessage = (input: SendZaloInput) => apiPost<{ msg_ids: string[]; client_ref: string | null; conversation_key: string }>('/zalo/messages', input)

export const ZALO_MAX_FILES = 5
