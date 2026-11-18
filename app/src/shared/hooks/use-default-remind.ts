import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/core/api/http-client'
import { queryKeys } from '@/shared/constants/query-keys'

// Nhắc mặc định cho sự kiện mới (khóa calendar.default_remind_minutes, đổi ở Cài đặt, Thông báo).
export function useDefaultRemind(): number | null {
  const settings = useQuery({
    queryKey: queryKeys.setting.values,
    queryFn: () => apiGet<{ values: Record<string, unknown> }>('/settings'),
    staleTime: 5 * 60_000,
  })
  const value = settings.data?.values['calendar.default_remind_minutes']
  return Array.isArray(value) && typeof value[0] === 'number' ? value[0] : 15
}
