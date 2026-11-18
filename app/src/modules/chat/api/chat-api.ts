import { apiDelete, apiGet, apiPost } from '@/core/api/http-client'
import type { ChatAction, ChatStatus, ChatToday } from '@/modules/chat/types/chat'

export const getChatToday = () => apiGet<ChatToday>('/chat/today')
export const getChatStatus = () => apiGet<ChatStatus>('/chat/status')
export const deleteConversation = (id: number) => apiDelete<null>(`/chat/conversations/${id}`)

const RESTORE_PATHS = { expense: '/expenses', task: '/tasks', event: '/calendar/events' } as const

// Hoàn tác xóa một dòng: POST /<resource>/{id}/restore (12-api.md mục 3.1, 3.9).
export async function restoreResources(action: Extract<ChatAction, { type: 'undo' }>): Promise<void> {
  const base = RESTORE_PATHS[action.resource]
  for (const id of action.ids) await apiPost(`${base}/${id}/restore`)
}

export const restoreProfileRevision = (undoVersion: number, currentVersion: number) =>
  apiPost(`/memory/profile/revisions/${undoVersion}/restore`, { version: currentVersion })
