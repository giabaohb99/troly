import { ChevronLeft, Reply } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { getThread } from '@/modules/inbox/api/gmail-api'
import { GmailConnectHint, isGmailNotConnected } from '@/modules/inbox/components/gmail-connect-hint'
import { ErrorState } from '@/shared/components/error-state'
import { RichText } from '@/shared/components/rich-text'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { Button } from '@/shared/ui/button'
import { formatDayTitle, formatTime, toDateKey } from '@/shared/utils/format'
import { reflowPlainText } from '@/shared/utils/text-tokens'

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
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-bold">{data?.subject || 'Thư'}</h1>
          {data?.account_email && <p className="truncate text-xs text-muted-foreground">Hộp thư {data.account_email}</p>}
        </div>
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
          {/* Phản hồi 1.0.8: link bấm mở trình duyệt (link dài thành chip tên miền), số bấm gọi, email bấm soạn thư;
              gộp dòng thư chữ bị ngắt giữa câu. Thư HTML vẫn tạm dừng (QĐ-48). */}
          <p className="break-words whitespace-pre-wrap">
            <RichText
              text={reflowPlainText(m.text)}
              compactLinks
              onEmail={(email) => navigate('/hop-tin/email/soan', { state: { to: [email], accountEmail: data?.account_email ?? null } })}
            />
          </p>
        </article>
      ))}
      {data?.reply && (
        <Button
          onClick={() =>
            navigate('/hop-tin/email/soan', {
              state: { to: data.reply?.to ?? [], cc: data.reply?.cc ?? [], subject: data.reply?.subject ?? `Re: ${data.subject}`, threadRef: data.thread_id, accountEmail: data.account_email ?? null },
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
