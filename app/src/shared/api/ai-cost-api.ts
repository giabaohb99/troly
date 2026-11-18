import { apiGet, toQuery } from '@/core/api/http-client'

// Chi phí AI theo tháng (12, GET /reports/ai-cost): dùng ở màn Báo cáo và Cài đặt, Chi phí AI.
export interface AiCost {
  // YYYY-MM
  month?: string
  total_usd: number
  today_usd: number
  monthly_warn_usd: number
  by_day: { date: string; usd: number }[]
  by_model: { model: string; usd: number }[]
  by_purpose: { purpose: string; usd: number }[]
  cache_read_ratio: number | null
}

export const getAiCost = (month: string) => apiGet<AiCost>(`/reports/ai-cost${toQuery({ month })}`)
