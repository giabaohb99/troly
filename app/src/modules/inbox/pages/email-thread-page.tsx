import { ChevronLeft, Reply } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { getThread } from '@/modules/inbox/api/gmail-api'
import { GmailConnectHint, isGmailNotConnected } from '@/modules/inbox/components/gmail-connect-hint'
import { ErrorState } from '@/shared/components/error-state'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { Button } from '@/shared/ui/button'
import { formatDayTitle, formatTime, toDateKey } from '@/shared/utils/format'

// Một luồng thư Gmail (QĐ-43): thư cũ trước, nút Trả lời mở màn soạn với người nhận và tiêu đề gợi ý sẵn.
export function EmailThreadPage() {
  const navigate = useNavigate()
  const threadId = useParams().threadId ?? ''
  const thread = useQuery({ queryKey: ['gmail', 'thread', threadId], queryFn: () => getThread(threadId), retry: 0 })
  const data = thread.data

  return (
    <div className="flex flex-col gap-4 pb-8">
      <div className="flex items-center gap-1">
        <Button size="icon" variant="ghost" aria-label="Quay lại" onClick={() => navigate('/hop-tin?loai=gmail')}>
          <ChevronLeft className="size-5" />
        </Button>
        <h1 className="min-w-0 flex-1 truncate text-lg font-bold">{data?.subject || 'Thư'}</h1>
      </div>
      {thread.isPending && <SkeletonList />}
      {thread.isError && (isGmailNotConnected(thread.error) ? <GmailConnectHint /> : <ErrorState error={thread.error} onRetry={() => void thread.refetch()} />)}
      {data?.messages.map((m) => (
        <article key={m.id} className="flex flex-col gap-2 rounded-2xl border bg-card p-4 text-sm">
          <header className="flex flex-col">
            <span className="font-semibold">{m.from_name || m.from_email}</span>
            <span className="text-xs text-muted-foreground">
              {m.from_name ? `${m.from_email} · ` : ''}
              {formatDayTitle(toDateKey(m.date))} {formatTime(m.date)}
            </span>
            {m.to.length > 0 && <span className="truncate text-xs text-muted-foreground">Tới: {m.to.join(', ')}</span>}
          </header>
          <p className="break-words whitespace-pre-wrap">{m.text}</p>
        </article>
      ))}
      {data?.reply && (
        <Button
          onClick={() =>
            navigate('/hop-tin/email/soan', {
              state: { to: data.reply?.to ?? [], cc: data.reply?.cc ?? [], subject: data.reply?.subject ?? `Re: ${data.subject}`, threadRef: data.thread_id },
            })
          }
        >
          <Reply className="size-4" />
          Trả lời
        </Button>
      )}
    </div>
  )
}
