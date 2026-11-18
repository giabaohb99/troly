import { WifiOff } from 'lucide-react'
import { useOnline } from '@/shared/hooks/use-online'

export function OfflineBanner() {
  const online = useOnline()
  if (online) return null
  return (
    <div className="flex items-center gap-2 rounded-xl border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning" role="status">
      <WifiOff className="size-4 shrink-0" />
      Mất mạng. Đang xem dữ liệu đã lưu; lưu và gửi cần mạng.
    </div>
  )
}
