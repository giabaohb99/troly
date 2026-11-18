import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Ban, CircleCheck, Clock, Loader2, RefreshCw, ShieldCheck, TriangleAlert } from 'lucide-react'
import { getErrorMessage } from '@/core/api/api-error'
import { Alarm } from '@/core/native/alarm'
import { approveAction, rejectAction } from '@/shared/api/pending-action-api'
import { queryKeys } from '@/shared/constants/query-keys'
import type { ConfirmInfo, PendingStatus } from '@/shared/types/pending-action'
import { Button } from '@/shared/ui/button'
import { formatTime } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

function hoursLeft(expiresAt: string, now = Date.now()): number {
  return Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / 3_600_000))
}

interface ConfirmCardProps {
  action: ConfirmInfo
  serverStatus?: PendingStatus
  className?: string
  onDecided?: (status: PendingStatus) => void
}

// Thẻ duyệt: chỉ cho gửi ra ngoài, xóa hàng loạt, xóa chuyến (QĐ-27). Duyệt chỉ bằng nút (31 mục 3.3).
export function ConfirmCard({ action, serverStatus, className, onDecided }: ConfirmCardProps) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<PendingStatus | null>(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [resultAt, setResultAt] = useState<string | null>(null)
  const sendingRef = useRef(false)
  const [openedAt] = useState(() => Date.now())
  const expired = Date.parse(action.expires_at) < openedAt
  const effective: PendingStatus = status ?? serverStatus ?? (expired ? 'expired' : 'pending')

  async function decide(approve: boolean) {
    if (sendingRef.current) return
    sendingRef.current = true
    setSending(true)
    setError('')
    try {
      let next: PendingStatus = 'rejected'
      if (approve) {
        const result = await approveAction(action.pending_action_id)
        next = result.action.status === 'pending' ? 'done' : result.action.status
      } else {
        await rejectAction(action.pending_action_id)
      }
      setStatus(next)
      setResultAt(new Date().toISOString())
      onDecided?.(next)
      void queryClient.invalidateQueries({ queryKey: queryKeys.chat.today })
      void queryClient.invalidateQueries({ queryKey: queryKeys.expense.all })
      void queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all })
      if (next === 'done') void Alarm.sync()
    } catch (err) {
      setError(getErrorMessage(err))
      setStatus('failed')
    } finally {
      sendingRef.current = false
      setSending(false)
    }
  }

  if (effective === 'done') {
    return (
      <p className="flex items-center gap-2 text-sm text-primary">
        <CircleCheck className="size-4" />
        Đã làm: {action.title}
        {resultAt && ` lúc ${formatTime(resultAt)}`}
      </p>
    )
  }
  if (effective === 'rejected') {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Ban className="size-4" />
        Đã bỏ: {action.title}
      </p>
    )
  }
  if (effective === 'expired') {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Clock className="size-4" />
        Hết hạn, nhắn lại nếu vẫn cần.
      </p>
    )
  }

  return (
    <div className={cn('w-full max-w-[92%] rounded-2xl border bg-card p-4', className, action.danger ? 'border-destructive/40' : 'border-primary/40')}>
      <p className="flex items-center gap-2 font-semibold">
        <ShieldCheck className={cn('size-5 shrink-0', action.danger ? 'text-destructive' : 'text-primary')} />
        {action.title}
      </p>
      {action.summary && <p className="mt-1 text-sm text-muted-foreground">{action.summary}</p>}
      {action.details.length > 0 && (
        <dl className="mt-3 flex flex-col gap-1 border-t pt-3 text-sm">
          {action.details.map((detail, index) => (
            <div key={index} className="flex gap-2">
              <dt className="shrink-0 text-muted-foreground">{detail.label}:</dt>
              <dd className="min-w-0 break-words whitespace-pre-wrap">{detail.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {effective === 'failed' && error && (
        <p className="mt-3 flex items-center gap-2 text-sm text-destructive">
          <TriangleAlert className="size-4 shrink-0" />
          {error}
        </p>
      )}
      <div className="mt-4 flex gap-2">
        {!sending && (
          <Button variant="outline" className="flex-1" onClick={() => void decide(false)}>
            {action.cancel_label || 'Bỏ'}
          </Button>
        )}
        <Button variant={action.danger ? 'destructive' : 'default'} className="flex-1" disabled={sending} onClick={() => void decide(true)}>
          {sending ? <Loader2 className="size-4 animate-spin" /> : effective === 'failed' ? <RefreshCw className="size-4" /> : null}
          {sending ? 'Đang làm...' : effective === 'failed' ? 'Thử lại' : action.confirm_label || 'Duyệt'}
        </Button>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">Hết hạn sau {hoursLeft(action.expires_at, openedAt)} giờ</p>
    </div>
  )
}
