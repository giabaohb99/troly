import { useQuery } from '@tanstack/react-query'
import { checkRelease } from '@/core/native/update'
import { queryKeys } from '@/shared/constants/query-keys'

// Kiểm bản mới khi mở app; giữ kết quả 6 giờ (lần mở app sau lại kiểm).
export function useRelease() {
  return useQuery({ queryKey: queryKeys.device.release, queryFn: checkRelease, staleTime: 6 * 3_600_000, retry: 0 })
}
