import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/core/api/http-client'

// Cờ tính năng (luật đợt 1.1.0): app đọc `features` từ /system/status và ẩn mục, nút, màn của tính năng chưa bật.
// Máy chủ cũ chưa có cờ, lỗi, hoặc đang tải thì coi như tắt.
export interface Features {
  gym: boolean
  connectors: boolean
  zalo_bridge: boolean
}

export const FEATURES_OFF: Features = { gym: false, connectors: false, zalo_bridge: false }
export const FEATURES_KEY = ['system', 'features'] as const

export function readFeatures(status: unknown): Features {
  const raw = (status as { features?: Partial<Record<keyof Features, unknown>> } | null)?.features
  if (!raw || typeof raw !== 'object') return FEATURES_OFF
  return { gym: raw.gym === true, connectors: raw.connectors === true, zalo_bridge: raw.zalo_bridge === true }
}

function useFeaturesQuery() {
  return useQuery({
    queryKey: FEATURES_KEY,
    queryFn: () => apiGet<unknown>('/system/status'),
    staleTime: 10 * 60_000,
    retry: 1,
    select: readFeatures,
  })
}

export function useFeatures(): Features {
  return useFeaturesQuery().data ?? FEATURES_OFF
}

// Cho màn chặn: biết đã có câu trả lời đầu chưa (lỗi cũng tính là đã có, coi như tắt).
export function useFeatureState(): { features: Features; loaded: boolean } {
  const query = useFeaturesQuery()
  return { features: query.data ?? FEATURES_OFF, loaded: !query.isPending }
}
