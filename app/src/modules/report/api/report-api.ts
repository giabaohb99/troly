import { apiGet, toQuery } from '@/core/api/http-client'

// Báo cáo (12 mục 5.1, dòng /reports). Dạng thẻ đã đề xuất cho agent kiến trúc ở mục 5 bảng việc.

export interface Card<T> {
  // disabled: thẻ chưa bật, message nói lý do.
  status: 'ok' | 'error' | 'disabled'
  data: T | null
  message: string | null
}

export interface Dashboard {
  date: string
  cards: {
    // period dạng YYYY-MM theo giờ Việt Nam.
    expense: Card<{ period: string; total_vnd: number; previous_total_vnd: number | null; income_vnd: number; top_categories: { name: string; total_vnd: number }[] }>
    calendar: Card<{ week_events: number; next_event: { id: number; title: string; start_at: string } | null }>
    tasks: Card<{ overdue: number; today: number; open: number }>
    inbox: Card<{ important_unseen: number; new_count: number }>
    ai: Card<{ month_usd: number; today_usd: number; monthly_warn_usd: number }>
    devices: Card<{ items: { id: number; name: string; listener_connected: boolean | null; last_event_at: string | null; otp_blocked_today: number; last_seen_at: string | null }[] }>
  }
}

export const getDashboard = (date: string) => apiGet<Dashboard>(`/reports/dashboard${toQuery({ date })}`)
