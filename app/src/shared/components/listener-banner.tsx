import { TriangleAlert } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { isNative } from '@/core/config'
import { usePermissions } from '@/shared/hooks/use-permissions'
import { Button } from '@/shared/ui/button'

// Dải báo thiếu quyền đọc thông báo ở Hộp tin, Chi tiêu (31 mục 3.4). Chỉ trên điện thoại.
export function ListenerBanner({ text }: { text: string }) {
  const navigate = useNavigate()
  const permissions = usePermissions()
  if (!isNative || !permissions.data || permissions.data.notificationListener) return null
  return (
    <div className="flex items-center gap-2 rounded-xl border border-warning/40 bg-warning/10 px-3 py-2 text-sm">
      <TriangleAlert className="size-4 shrink-0 text-warning" />
      <span className="min-w-0 flex-1">{text}</span>
      <Button size="sm" variant="secondary" onClick={() => navigate('/thiet-lap')}>
        Bật
      </Button>
    </div>
  )
}
