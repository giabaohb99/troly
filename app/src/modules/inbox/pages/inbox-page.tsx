import { useMemo } from 'react'
import { Inbox, Loader2, PenSquare, Sparkles, Star } from 'lucide-react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { isNative } from '@/core/config'
import { Notify } from '@/core/native/notify'
import { threadIdFromKey } from '@/modules/inbox/api/gmail-api'
import { listConversations, type ConversationFilters } from '@/modules/inbox/api/inbox-api'
import { AppTag } from '@/modules/inbox/components/app-tag'
import { APP_LABELS, type Conversation, type InboxApp } from '@/modules/inbox/types/inbox'
import { queryKeys } from '@/shared/constants/query-keys'
import { EmptyState } from '@/shared/components/empty-state'
import { ErrorState } from '@/shared/components/error-state'
import { ListenerBanner } from '@/shared/components/listener-banner'
import { OfflineBanner } from '@/shared/components/offline-banner'
import { PageHeader } from '@/shared/components/page-header'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { Button } from '@/shared/ui/button'
import { formatWhen } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

type FilterValue = 'important' | 'all' | InboxApp
const FILTERS: { value: FilterValue; label: string }[] = [
  { value: 'important', label: 'Quan trọng' },
  { value: 'all', label: 'Tất cả' },
  // QĐ-42: bỏ tab Tele, Mess; Email thêm sau.
  ...(['zalo', 'sms'] as const).map((app) => ({ value: app, label: APP_LABELS[app] })),
  // QĐ-43: thư Gmail (người gửi, tiêu đề, đoạn trích); bấm mở luồng thư.
  { value: 'gmail', label: 'Email' },
]

function toFilters(value: FilterValue): ConversationFilters {
  if (value === 'important') return { app: null, importance: 'important' }
  if (value === 'all') return { app: null, importance: null }
  return { app: value, importance: null }
}

function summaryPrompt(value: FilterValue): string {
  if (value === 'important') return 'Tóm tắt tin quan trọng hôm nay'
  if (value === 'all') return 'Tóm tắt tin nhắn hôm nay'
  return `Tóm tắt tin ${APP_LABELS[value]} hôm nay`
}

function ConversationRow({ item, onOpen }: { item: Conversation; onOpen: () => void }) {
  const unread = item.unread_count > 0
  const preview = item.is_group && item.last_sender ? `${item.last_sender}: ${item.last_text ?? ''}` : (item.last_text ?? '')
  return (
    <button type="button" onClick={onOpen} className="flex w-full items-start gap-2 py-2.5 text-left">
      <span className="mt-0.5 w-4 shrink-0">{item.importance === 'important' && <Star className="size-4 text-warning" />}</span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <AppTag app={item.app} />
          <span className={cn('min-w-0 flex-1 truncate', unread ? 'font-semibold' : 'font-medium')}>{item.title ?? 'Không rõ'}</span>
          <span className="shrink-0 text-xs text-muted-foreground">{formatWhen(item.last_posted_at)}</span>
        </span>
        {item.app === 'gmail' && item.last_sender && <span className="mt-0.5 block truncate text-xs text-muted-foreground">{item.last_sender}</span>}
        <span className="mt-0.5 flex items-center gap-2">
          <span className={cn('line-clamp-1 min-w-0 flex-1 text-sm', unread ? 'text-foreground' : 'text-muted-foreground')}>{preview}</span>
          {unread && <span className="shrink-0 rounded-full bg-primary px-1.5 text-xs font-semibold text-primary-foreground">{item.unread_count}</span>}
        </span>
      </span>
    </button>
  )
}

// Màn Hộp tin (31 mục 3.5): mỗi dòng một cuộc trò chuyện theo conversation_key; Tóm tắt là câu chat dựng sẵn.
export function InboxPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const filter: FilterValue = (FILTERS.find((f) => f.value === params.get('loai'))?.value ?? 'all') as FilterValue
  const setFilter = (value: FilterValue) => setParams(value === 'all' ? {} : { loai: value }, { replace: true })
  const filters = toFilters(filter)
  const list = useInfiniteQuery({
    queryKey: queryKeys.inbox.conversations({ ...filters }),
    queryFn: ({ pageParam }) => listConversations(filters, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  })
  const status = useQuery({ queryKey: queryKeys.device.notifyStatus, queryFn: async () => ({ ...(await Notify.getStatus()), checkedAt: Date.now() }), enabled: isNative })
  const items = useMemo(() => (list.data?.pages ?? []).flatMap((page) => page.items), [list.data])
  const unreadTotal = items.reduce((sum, c) => sum + c.unread_count, 0)
  const silentHours = status.data?.listenerConnected && status.data.lastEventAt ? Math.floor((status.data.checkedAt - status.data.lastEventAt) / 3_600_000) : null

  return (
    <div className="flex flex-col gap-4 pb-8">
      <PageHeader
        title="Hộp tin"
        subtitle={list.isSuccess ? (unreadTotal > 0 ? `${unreadTotal} tin mới` : 'Đã xem hết') : undefined}
        actions={
          <Button variant="ghost" size="icon" aria-label="Tóm tắt" onClick={() => navigate(`/?tom-tat=${encodeURIComponent(summaryPrompt(filter))}`)}>
            <Sparkles className="size-5" />
          </Button>
        }
      />
      <OfflineBanner />
      <ListenerBanner text="Chưa bật đọc thông báo nên chưa nhận tin mới." />
      {silentHours !== null && silentHours >= 24 && (
        <div className="flex items-center gap-2 rounded-xl border border-info/40 bg-info/10 px-3 py-2 text-sm">
          <span className="min-w-0 flex-1">Đã {silentHours} giờ chưa nhận tin nào. Kiểm tra pin và chế độ ngủ của Samsung.</span>
          <Button size="sm" variant="secondary" onClick={() => navigate('/thiet-lap')}>
            Kiểm tra
          </Button>
        </div>
      )}

      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setFilter(f.value)}
            className={cn('shrink-0 rounded-full border px-3 py-1 text-sm', filter === f.value && 'border-primary bg-primary/15 text-primary')}
          >
            {f.label}
          </button>
        ))}
      </div>

      {list.isPending && <SkeletonList />}
      {list.isError && <ErrorState error={list.error} onRetry={() => void list.refetch()} />}
      {list.isSuccess && items.length === 0 && (
        <EmptyState
          icon={Inbox}
          text={filter === 'important' ? 'Không có tin quan trọng nào cần xử lý.' : 'Chưa có tin nào. Tin Zalo, SMS hiện ở đây khi điện thoại nhận thông báo.'}
        />
      )}

      {items.length > 0 && (
        <div className="divide-y">
          {items.map((item) => (
            <ConversationRow
              key={item.conversation_key}
              item={item}
              onOpen={() =>
                navigate(item.app === 'gmail' ? `/hop-tin/email/${encodeURIComponent(threadIdFromKey(item.conversation_key))}` : `/hop-tin/${encodeURIComponent(item.conversation_key)}`)
              }
            />
          ))}
        </div>
      )}

      {list.hasNextPage && (
        <Button variant="secondary" disabled={list.isFetchingNextPage} onClick={() => void list.fetchNextPage()}>
          {list.isFetchingNextPage && <Loader2 className="size-4 animate-spin" />}
          Xem thêm
        </Button>
      )}
      {items.length > 0 && <p className="text-center text-xs text-muted-foreground">Tin giữ 180 ngày rồi tự xóa.</p>}
      {filter === 'gmail' && (
        <Button
          size="icon"
          aria-label="Soạn thư mới"
          className="fixed right-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-30 size-14 rounded-full shadow-lg"
          onClick={() => navigate('/hop-tin/email/soan')}
        >
          <PenSquare className="size-6" />
        </Button>
      )}
    </div>
  )
}
