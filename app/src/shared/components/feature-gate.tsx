import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useFeatureState, type Features } from '@/shared/hooks/use-features'

// Màn của tính năng chưa bật (cờ trong /system/status): về Cài đặt thay vì hiện màn dở (luật đợt 1.1.0).
export function FeatureGate({ flag, children, fallback = '/cai-dat' }: { flag: keyof Features; children: ReactNode; fallback?: string }) {
  const { features, loaded } = useFeatureState()
  // Chờ câu trả lời đầu (mở từ đường dẫn sâu), không thì chuyển trang sớm.
  if (!loaded) return null
  return features[flag] ? <>{children}</> : <Navigate to={fallback} replace />
}
