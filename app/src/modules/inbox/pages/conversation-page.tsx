import { useEffect, useMemo, useRef } from 'react'
import { Bot, Check, ChevronLeft, Loader2 } from 'lucide-react'
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { listMessages, markConversation } from '@/modules/inbox/api/inbox-api'
import { AppTag } from '@/modules/inbox/components/app-tag'
import { queryKeys } from '@/shared/constants/query-keys'
import { ErrorState } from '@/shared/components/error-state'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { Button } from '@/shared/ui/button'
import { formatWhen } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

// Một cuộc trò chuyện trong Hộp tin: tin theo giờ, mở là đánh dấu đã xem.
export function ConversationPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const key = useParams().conversationKey ?? ''
  const markedRef = useRef(false)
  const messages = useInfiniteQuery({
    queryKey: queryKeys.inbox.messages(key),
    queryFn: ({ pageParam }) => listMessages(key, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  })
  // Trang đầu là tin mới nhất; ghép các trang rồi sắp cũ trước để đọc từ trên xuống.
  const items = useMemo(
    () => (messages.data?.pages ?? []).flatMap((p) => p.items).sort((a, b) => Date.parse(a.posted_at) - Date.parse(b.posted_at)),
    [messages.data],
  )
  const first = items[0]
  const title = first?.conversation_title ?? items.find((m) => m.sender)?.sender ?? 'Cuộc trò chuyện'

  useEffect(() => {
    if (markedRef.current || !items.some((m) => m.status === 'new')) return
    markedRef.current = true
    void markConversation(key, 'seen').then(() => queryClient.invalidateQueries({ queryKey: queryKeys.inbox.all }))
  }, [items, key, queryClient])

  async function markDone() {
    try {
      await markConversation(key, 'done')
      await queryClient.invalidateQueries({ queryKey: queryKeys.inbox.all })
      toast.success('Đã đánh dấu xử lý')
      navigate('/hop-tin')
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  return (
    <div className="flex flex-col gap-4 pb-8">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" aria-label="Quay lại" onClick={() => navigate('/hop-tin')}>
          <ChevronLeft className="size-5" />
        </Button>
        {first && <AppTag app={first.app} />}
        <h1 className="min-w-0 flex-1 truncate text-lg font-semibold">{title}</h1>
      </div>

      {messages.hasNextPage && (
        <Button variant="ghost" size="sm" disabled={messages.isFetchingNextPage} onClick={() => void messages.fetchNextPage()}>
          {messages.isFetchingNextPage && <Loader2 className="size-4 animate-spin" />}
          Tin cũ hơn
        </Button>
      )}
      {messages.isPending && <SkeletonList rows={5} />}
      {messages.isError && <ErrorState error={messages.error} onRetry={() => void messages.refetch()} />}

      <div className="flex flex-col gap-3">
        {items.map((m) => (
          <div key={m.id} className="flex flex-col gap-0.5">
            <span className="text-xs text-muted-foreground">
              {m.is_group && m.sender ? `${m.sender} · ` : ''}
              {formatWhen(m.posted_at)}
              {m.importance === 'important' && m.importance_reason ? ` · ${m.importance_reason}` : ''}
            </span>
            <p className={cn('max-w-[90%] rounded-2xl rounded-tl-md border bg-card px-4 py-2 text-[15px] whitespace-pre-wrap break-words', m.hidden_content && 'text-muted-foreground italic')}>
              {m.subject ? <strong className="block">{m.subject}</strong> : null}
              {m.text}
            </p>
          </div>
        ))}
      </div>

      {items.length > 0 && (
        <div className="flex flex-col gap-2">
          <Button onClick={() => void markDone()}>
            <Check className="size-4" />
            Đã xử lý
          </Button>
          <Button variant="secondary" onClick={() => navigate(`/?hoi=${encodeURIComponent(`Cuộc trò chuyện ${title} trên ${first?.app ?? ''}: `)}`)}>
            <Bot className="size-4" />
            Hỏi trợ lý về cuộc này
          </Button>
        </div>
      )}
    </div>
  )
}
