import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Ban, CircleCheck, Clock, Loader2, RefreshCw, ShieldCheck, TriangleAlert } from 'lucide-react'
import { getErrorMessage } from '@/core/api/api-error'
import { Alarm } from '@/core/native/alarm'
import { approveAction, getActionStatus, rejectAction } from '@/shared/api/pending-action-api'
import { queryKeys } from '@/shared/constants/query-keys'
import type { ConfirmInfo, PendingStatus } from '@/shared/types/pending-action'
import { Button } from '@/shared/ui/button'
import { classifyDecisionError, decidedLabel, extraResult, initialStatus, isFinalStatus, outcomeFromAction, outcomeFromServer, type CardOutcome } from '@/shared/utils/pending-decision'
import { cn } from '@/shared/utils/cn'

function hoursLeft(expiresAt: string, now = Date.now()): number {
  return Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / 3_600_000))
}

interface ConfirmCardProps {
  action: ConfirmInfo
  serverStatus?: PendingStatus
  // Thẻ trong lịch sử: trạng thái trong tin chưa phải đã quyết thì hỏi máy chủ trạng thái thật trước khi hiện nút.
  lookupStatus?: boolean
  className?: string
  onDecided?: (status: PendingStatus) => void
}

// Thẻ duyệt: chỉ cho gửi ra ngoài, xóa hàng loạt, xóa chuyến (QĐ-27). Duyệt chỉ bằng nút (31 mục 3.3).
// Dùng trạng thái máy chủ; gặp 409 thì tải lại trạng thái và hiện kết quả cuối (lỗi thẻ kẹt ở bản 1.0.1).
export function ConfirmCard({ action, serverStatus, lookupStatus, className, onDecided }: ConfirmCardProps) {
  const queryClient = useQueryClient()
  const [outcome, setOutcome] = useState<CardOutcome | null>(null)
  const [sending, setSending] = useState(false)
  const sendingRef = useRef(false)
  const [openedAt] = useState(() => Date.now())
  const lookup = useQuery({
    queryKey: ['pending-action', action.pending_action_id],
    queryFn: () => getActionStatus(action.pending_action_id),
    enabled: !!lookupStatus && !outcome && !isFinalStatus(action.status),
    // Kết quả còn chờ thì hỏi lại mỗi lần mở (có thể đã duyệt ở nơi khác); đã quyết thì không đổi.
    staleTime: (query) => (query.state.data?.status === 'pending' ? 0 : 60_000),
  })
  const checking = lookup.isPending || (lookup.isFetching && lookup.data?.status === 'pending')
  const looked = lookup.data ? outcomeFromServer(lookup.data) : null
  const current: CardOutcome = outcome ??
    looked ?? {
      status: initialStatus(action.status, serverStatus),
      reason: action.error ?? null,
      transient: false,
      decidedAt: action.decided_at ?? null,
      resultText: action.result_text ?? null,
    }

  const finish = (next: CardOutcome) => {
    setOutcome(next)
    onDecided?.(next.status)
    void queryClient.invalidateQueries({ queryKey: queryKeys.chat.today })
    void queryClient.invalidateQueries({ queryKey: ['pending-action', action.pending_action_id] })
    void queryClient.invalidateQueries({ queryKey: queryKeys.expense.all })
    void queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all })
    void queryClient.invalidateQueries({ queryKey: queryKeys.trip.all })
    if (next.status === 'done') void Alarm.sync()
  }

  async function decide(approve: boolean) {
    if (sendingRef.current) return
    sendingRef.current = true
    setSending(true)
    try {
      if (approve) {
        const result = await approveAction(action.pending_action_id)
        finish(outcomeFromAction(result.action, result.result_text))
      } else {
        const result = await rejectAction(action.pending_action_id)
        finish(outcomeFromAction({ ...result.action, status: result.action.status === 'pending' ? 'rejected' : result.action.status }))
      }
    } catch (err) {
      const kind = classifyDecisionError(err)
      if (kind === 'refetch') {
        // Máy chủ đã xử lý hoặc hết hạn: lấy trạng thái thật, không hiện lại nút.
        const real = await getActionStatus(action.pending_action_id).catch(() => null)
        const next = real ? outcomeFromServer(real) : { status: 'expired' as const, reason: null, transient: false }
        // Bấm Bỏ mà máy chủ vẫn giữ failed: coi như đã bỏ trên máy này.
        finish(!approve && next.status === 'failed' ? { status: 'rejected', reason: null, transient: false } : next)
      } else if (!approve && current.status === 'failed') {
        finish({ status: 'rejected', reason: null, transient: false })
      } else {
        setOutcome({ status: 'failed', reason: getErrorMessage(err), transient: kind === 'transient' })
      }
    } finally {
      sendingRef.current = false
      setSending(false)
    }
  }

  if (lookupStatus && !outcome && !isFinalStatus(action.status) && checking) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        {action.title}
      </p>
    )
  }
  if (current.status === 'done') {
    return (
      <p className="flex items-center gap-2 text-sm text-primary">
        <CircleCheck className="size-4" />
        <span className="min-w-0">
          Đã làm: {action.title}
          {decidedLabel(current.decidedAt) && ` ${decidedLabel(current.decidedAt)}`}
          {extraResult(current.resultText) && <span className="text-muted-foreground"> · {extraResult(current.resultText)}</span>}
        </span>
      </p>
    )
  }
  if (current.status === 'rejected') {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Ban className="size-4" />
        Đã bỏ: {action.title}
      </p>
    )
  }
  if (current.status === 'expired') {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Clock className="size-4" />
        Hết hạn, nhắn lại nếu vẫn cần.
      </p>
    )
  }

  const failed = current.status === 'failed'
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
      {failed && (
        <p className="mt-3 flex items-start gap-2 text-sm text-destructive">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          {current.reason ?? 'Không làm được việc này.'}
        </p>
      )}
      <div className="mt-4 flex gap-2">
        {!sending && (
          <Button variant="outline" className="flex-1" onClick={() => void decide(false)}>
            {action.cancel_label || 'Bỏ'}
          </Button>
        )}
        {(!failed || current.transient) && (
          <Button variant={action.danger ? 'destructive' : 'default'} className="flex-1" disabled={sending} onClick={() => void decide(true)}>
            {sending ? <Loader2 className="size-4 animate-spin" /> : failed ? <RefreshCw className="size-4" /> : null}
            {sending ? 'Đang làm...' : failed ? 'Thử lại' : action.confirm_label || 'Duyệt'}
          </Button>
        )}
      </div>
      {!failed && <p className="mt-2 text-xs text-muted-foreground">Hết hạn sau {hoursLeft(action.expires_at, openedAt)} giờ</p>}
    </div>
  )
}
