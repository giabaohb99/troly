import { useEffect, useMemo, useRef, useState } from 'react'
import { Bot, Check, ChevronLeft, ExternalLink, Loader2, MessageSquare } from 'lucide-react'
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { isNative } from '@/core/config'
import { Notify } from '@/core/native/notify'
import { listMessages, markConversation } from '@/modules/inbox/api/inbox-api'
import { linkZaloConversation } from '@/modules/inbox/api/zalo-api'
import { useFeatures } from '@/shared/hooks/use-features'
import { AppTag } from '@/modules/inbox/components/app-tag'
import { queryKeys } from '@/shared/constants/query-keys'
import { ErrorState } from '@/shared/components/error-state'
import { RichText } from '@/shared/components/rich-text'
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

  // Zalo qua zca-js (QĐ-52): cuộc đọc từ thông báo tự nối với danh bạ Zalo rồi mở khung chat nhắn được. Không khớp
  // đúng một người, nhóm cùng tên thì để nút chọn trong danh bạ.
  const features = useFeatures()
  const zaloBridge = first?.app === 'zalo' && !!features.zalo_bridge
  const [linking, setLinking] = useState<'idle' | 'trying' | 'failed'>('idle')
  useEffect(() => {
    if (!zaloBridge || linking !== 'idle') return
    setLinking('trying')
    linkZaloConversation(key)
      .then(({ conversation_key }) => {
        void queryClient.invalidateQueries({ queryKey: queryKeys.inbox.all })
        navigate(`/zalo/${encodeURIComponent(conversation_key)}`, { replace: true })
      })
      .catch(() => setLinking('failed'))
  }, [zaloBridge, linking, key, navigate, queryClient])

  // Zalo không gửi thay (QĐ-43): mở đúng cuộc chat qua thông báo gốc nếu còn, không thì mở app Zalo.
  const canOpenSource = first?.app === 'zalo'
  async function openSource() {
    if (!isNative) {
      toast.info('Mở Zalo chỉ có trên điện thoại.')
      return
    }
    const titles = [first?.conversation_title, ...items.map((m) => m.sender)].filter((t): t is string => !!t)
    const result = await Notify.openSource({ packageName: 'com.zing.zalo', titles: [...new Set(titles)] }).catch(() => ({ opened: null }))
    if (!result.opened) toast.error('Không mở được Zalo trên máy này.')
  }

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
          <div
            key={m.id}
            className={cn('flex flex-col gap-0.5', canOpenSource && 'cursor-pointer')}
            onClick={canOpenSource ? () => void openSource() : undefined}
          >
            <span className="text-xs text-muted-foreground">
              {m.is_group && m.sender ? `${m.sender} · ` : ''}
              {formatWhen(m.posted_at)}
              {m.importance === 'important' && m.importance_reason ? ` · ${m.importance_reason}` : ''}
            </span>
            <p className={cn('max-w-[90%] rounded-2xl rounded-tl-md border bg-card px-4 py-2 text-[15px] whitespace-pre-wrap break-words', m.hidden_content && 'text-muted-foreground italic')}>
              {m.subject ? <strong className="block">{m.subject}</strong> : null}
              {/* Link bấm được (link dài thành chip tên miền), số bấm gọi, email bấm soạn thư (phản hồi 1.0.8). */}
              {m.text && !m.hidden_content ? (
                <RichText text={m.text} compactLinks onEmail={(email) => navigate('/hop-tin/email/soan', { state: { to: [email] } })} />
              ) : (
                m.text
              )}
            </p>
          </div>
        ))}
      </div>

      {items.length > 0 && (
        <div className="flex flex-col gap-2">
          {zaloBridge && (
            <Button disabled={linking === 'trying'} onClick={() => navigate(`/zalo/moi?q=${encodeURIComponent(title)}`)}>
              {linking === 'trying' ? <Loader2 className="size-4 animate-spin" /> : <MessageSquare className="size-4" />}
              {linking === 'trying' ? 'Đang tìm trong danh bạ Zalo' : 'Nhắn Zalo'}
            </Button>
          )}
          {canOpenSource && (
            <Button variant="outline" onClick={() => void openSource()}>
              <ExternalLink className="size-4" />
              Mở trong Zalo
            </Button>
          )}
          <Button variant={zaloBridge ? 'outline' : 'default'} onClick={() => void markDone()}>
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
