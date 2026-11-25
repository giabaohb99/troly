import { apiDelete, apiGet, apiPatch, apiPost, toQuery } from '@/core/api/http-client'
import type { ChatAction, ChatMessage, ChatSession, ChatStatus, ChatToday } from '@/modules/chat/types/chat'

export const getChatToday = () => apiGet<ChatToday>('/chat/today')
export const getChatStatus = () => apiGet<ChatStatus>('/chat/status')
// Một trang tin của phiên, cũ trước; next_cursor là id tin cũ nhất của trang, null khi hết.
export const listConversationMessages = (conversationId: number, cursor: string | null, limit: number) =>
  apiGet<{ items: ChatMessage[]; next_cursor: string | null }>(`/chat/conversations/${conversationId}/messages${toQuery({ cursor, limit })}`)
export const deleteConversation = (id: number) => apiDelete<null>(`/chat/conversations/${id}`)

// Phiên chat (QĐ-51 bước 1): danh sách ghim trước rồi theo lần nhắn cuối; mở một phiên trả dạng như /chat/today.
export const listSessions = (q: string, cursor: string | null) =>
  apiGet<{ items: ChatSession[]; next_cursor: string | null }>(`/chat/conversations${toQuery({ q: q.trim() || undefined, cursor, limit: 50 })}`)
// Mở một phiên: cùng dạng /chat/today (phiên, 50 tin mới nhất, next_cursor, việc chờ duyệt); không có phiên thì 404.
export const getSession = (id: number) => apiGet<ChatToday>(`/chat/conversations/${id}`)
export const createSession = (title?: string) => apiPost<ChatSession>('/chat/conversations', title ? { title } : {})
export const updateSession = (id: number, patch: { title?: string; pinned?: boolean }) => apiPatch<ChatSession>(`/chat/conversations/${id}`, patch)

const RESTORE_PATHS = { expense: '/expenses', task: '/tasks', event: '/calendar/events' } as const

// Hoàn tác xóa một dòng: POST /<resource>/{id}/restore (12-api.md mục 3.1, 3.9).
export async function restoreResources(action: Extract<ChatAction, { type: 'undo' }>): Promise<void> {
  const base = RESTORE_PATHS[action.resource]
  for (const id of action.ids) await apiPost(`${base}/${id}/restore`)
}

export const restoreProfileRevision = (undoVersion: number, currentVersion: number) =>
  apiPost(`/memory/profile/revisions/${undoVersion}/restore`, { version: currentVersion })
