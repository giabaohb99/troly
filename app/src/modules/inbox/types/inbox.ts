// Theo backend/app/modules/inbox/service.py (12 mục 5.4).

export type InboxApp = 'zalo' | 'telegram' | 'messenger' | 'sms' | 'gmail' | 'other'
export type InboxStatus = 'new' | 'seen' | 'done'

export interface Conversation {
  conversation_key: string
  app: InboxApp
  title: string | null
  is_group: boolean
  last_sender: string | null
  last_text: string | null
  last_posted_at: string
  unread_count: number
  importance: 'normal' | 'important'
  is_private: boolean
}

export interface InboxMessage {
  id: number
  source: string
  app: InboxApp
  sender: string | null
  conversation_key: string
  conversation_title: string | null
  is_group: boolean
  subject: string | null
  text: string | null
  hidden_content: boolean
  posted_at: string
  status: InboxStatus
  importance: 'normal' | 'important'
  importance_reason: string | null
}

export const APP_LABELS: Record<InboxApp, string> = {
  zalo: 'Zalo',
  telegram: 'Tele',
  messenger: 'Mess',
  sms: 'SMS',
  gmail: 'Gmail',
  other: 'Khác',
}

// Màu nhãn app là token --app-1..6 (31 mục 3.1).
export const APP_COLORS: Record<InboxApp, string> = {
  zalo: 'bg-app-2/20 text-app-2',
  telegram: 'bg-app-6/20 text-app-6',
  messenger: 'bg-app-4/20 text-app-4',
  sms: 'bg-app-1/20 text-app-1',
  gmail: 'bg-app-5/20 text-app-5',
  other: 'bg-secondary text-muted-foreground',
}
