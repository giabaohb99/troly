import { MailWarning } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '@/core/api/api-error'
import { Button } from '@/shared/ui/button'

export const isGmailNotConnected = (error: unknown) => error instanceof ApiError && error.code === 'GOOGLE_NOT_CONNECTED'

// Chưa cấp gói Gmail: mời sang Cài đặt, Kết nối Google để cấp quyền.
export function GmailConnectHint() {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col items-start gap-2 rounded-2xl border bg-card p-4 text-sm">
      <p className="flex items-center gap-2 font-medium">
        <MailWarning className="size-4 text-warning" />
        Chưa cấp quyền Gmail
      </p>
      <p className="text-muted-foreground">Cấp quyền để đọc thư, trả lời và gửi thư mới qua thẻ duyệt.</p>
      <Button size="sm" onClick={() => navigate('/cai-dat/google')}>
        Cấp quyền Gmail
      </Button>
    </div>
  )
}
