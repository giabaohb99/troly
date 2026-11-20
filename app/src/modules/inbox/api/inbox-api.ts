import { apiGet, apiPost, toQuery } from '@/core/api/http-client'
import type { Conversation, InboxApp, InboxMessage, InboxStatus } from '@/modules/inbox/types/inbox'

export interface ConversationFilters {
  app: InboxApp | null
  importance: 'important' | null
  // Tab Email: chỉ thư của một tài khoản nhận (tham số `account_email`, không phân biệt hoa thường).
  account?: string | null
}

export const listConversations = (filters: ConversationFilters, cursor: string | null) =>
  apiGet<{ items: Conversation[]; next_cursor: string | null; accounts?: string[] }>(`/inbox/conversations${toQuery({ app: filters.app, importance: filters.importance, account_email: filters.account ?? undefined, cursor, limit: 30 })}`)

export const listMessages = (key: string, cursor: string | null) =>
  apiGet<{ items: InboxMessage[]; next_cursor: string | null }>(`/inbox/conversations/${encodeURIComponent(key)}/messages${toQuery({ cursor, limit: 100 })}`)

export const markConversation = (key: string, status: InboxStatus) =>
  apiPost<{ updated: number }>(`/inbox/conversations/${encodeURIComponent(key)}/mark`, { status })
