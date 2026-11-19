import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Bot, Info, Loader2, RefreshCw, Search, Trash2, TriangleAlert } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { deleteConversation } from '@/modules/chat/api/chat-api'
import { ActionList } from '@/modules/chat/components/action-list'
import { Composer } from '@/modules/chat/components/composer'
import { MessageBubble } from '@/modules/chat/components/message-bubble'
import { PastConversation } from '@/modules/chat/components/past-conversation'
import { useChatStatus, useChatToday, useChatTurn } from '@/modules/chat/hooks/use-chat'
import { queryKeys } from '@/shared/constants/query-keys'
import { ErrorState } from '@/shared/components/error-state'
import { OfflineBanner } from '@/shared/components/offline-banner'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { UpdateBanner } from '@/shared/components/update-banner'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { formatUsd } from '@/shared/utils/format'
import { openFileById } from '@/shared/utils/open-file'
import { useOlderMessages } from '@/modules/chat/hooks/use-older-messages'
import { mergeOlder } from '@/modules/chat/utils/older-messages'
import { Alarm } from '@/core/native/alarm'

// Mở từ thông báo tới tin cũ: tải thêm tối đa chừng này trang (50 tin mỗi trang) để tìm.
const MAX_SEEK_PAGES = 20

const SUGGESTIONS = ['cơm trưa 45k', 'Tháng này tiêu bao nhiêu rồi?', 'Tìm ghi chú về hợp đồng nhà', 'Giá vàng hôm nay']

// Màn chính (31 mục 3.5): tin hôm nay, lượt đang chạy qua SSE, hành động, ô nhập cố định phía dưới.
export function ChatPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const today = useChatToday()
  const status = useChatStatus()
  const { turn, send, retry, dismiss, busy } = useChatTurn()
  const [params, setParams] = useSearchParams()
  const [draft, setDraft] = useState(() => params.get('hoi') ?? '')
  const bottomRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const latest = today.data?.messages ?? []
  // Chỉ tải 50 tin mới nhất; kéo lên gần đầu thì tải trang cũ hơn, giữ nguyên chỗ đang đọc.
  const olderPages = useOlderMessages(today.data?.conversation?.id ?? null, today.data?.next_cursor ?? null)
  const messages = mergeOlder(olderPages.older, latest)
  const lastId = latest[latest.length - 1]?.id ?? null
  const keepFromBottomRef = useRef<number | null>(null)

  // Tin trả lời đã hiện trong màn chat thì coi như đã đọc: lớp gốc bỏ notice chat_done của chúng (lỗi 1.0.2).
  useEffect(() => {
    if (!lastId) return
    const ids = latest.filter((m) => m.role === 'assistant' && m.id > 0).slice(-20).map((m) => m.id)
    if (ids.length) void Alarm.markChatSeen({ messageIds: ids })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chạy lại khi có tin mới nhất khác
  }, [lastId])

  const loadOlder = async () => {
    const el = listRef.current
    if (!el || olderPages.loading || !olderPages.hasMore) return []
    keepFromBottomRef.current = el.scrollHeight - el.scrollTop
    return olderPages.loadOlder()
  }

  // Sau khi chèn tin cũ lên đầu: giữ khoảng cách tới đáy như trước khi tải để màn không nhảy.
  useLayoutEffect(() => {
    const el = listRef.current
    if (!el || keepFromBottomRef.current === null) return
    el.scrollTop = el.scrollHeight - keepFromBottomRef.current
    keepFromBottomRef.current = null
  }, [olderPages.older.length])

  // Từ màn Tìm: "Hỏi trợ lý" đưa câu vào ô nhập (/?hoi=...).
  useEffect(() => {
    if (params.get('hoi')) setParams({}, { replace: true })
  }, [params, setParams])

  // Từ Hộp tin: nút Tóm tắt gửi câu dựng sẵn với mode = summary (12 mục 5.2), không có endpoint riêng.
  const summaryRef = useRef(false)
  useEffect(() => {
    const prompt = params.get('tom-tat')
    if (!prompt || summaryRef.current) return
    summaryRef.current = true
    setParams({}, { replace: true })
    void send({ text: prompt, mode: 'summary', fileIds: [] })
  }, [params, setParams, send])

  // Mở màn chat: đứng ngay ở tin cuối, không có hiệu ứng cuộn (đặt scrollTop trước khi vẽ). Sau đó chỉ cuộn mượt
  // khi có tin mới mà người dùng đang ở cuối; tự gửi tin thì luôn xuống cuối. Mở tới một tin cụ thể thì không đụng.
  const seekingRef = useRef(false)
  seekingRef.current = !!params.get('tin')
  const positionedRef = useRef(false)
  const atBottomRef = useRef(true)
  useLayoutEffect(() => {
    const el = listRef.current
    if (!el || positionedRef.current || !lastId || seekingRef.current) return
    el.scrollTop = el.scrollHeight
    positionedRef.current = true
  }, [lastId])
  useEffect(() => {
    if (!positionedRef.current || seekingRef.current || !atBottomRef.current) return
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [lastId, turn?.text, turn?.actions.length, turn?.status])
  useEffect(() => {
    if (!turn?.clientMessageId) return
    atBottomRef.current = true
    positionedRef.current = true
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turn?.clientMessageId])

  // Từ thông báo trợ lý trả lời (QĐ-41): cuộn tới đúng tin, tin có tệp thì mở tệp khi bấm Mở tệp.
  const targetMessage = Number(params.get('tin')) || null
  const seekPagesRef = useRef(0)
  const fileToOpen = Number(params.get('mo-tep')) || null
  useEffect(() => {
    if (!targetMessage && !fileToOpen) return
    if (fileToOpen) void openFileById(fileToOpen)
    if (!targetMessage || !today.isSuccess) {
      if (fileToOpen)
        setParams(
          (prev) => {
            prev.delete('mo-tep')
            return prev
          },
          { replace: true },
        )
      return
    }
    const found = messages.some((m) => m.id === targetMessage)
    if (!found && olderPages.hasMore) {
      if (!olderPages.loading && seekPagesRef.current < MAX_SEEK_PAGES) {
        seekPagesRef.current += 1
        void loadOlder()
      }
      return
    }
    const timer = setTimeout(() => {
      seekPagesRef.current = 0
      document.getElementById(`tin-${targetMessage}`)?.scrollIntoView({ block: 'start' })
      positionedRef.current = true
      atBottomRef.current = false
      setParams(
        (prev) => {
          prev.delete('tin')
          prev.delete('mo-tep')
          return prev
        },
        { replace: true },
      )
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadOlder đổi mỗi lần vẽ; chạy lại theo số tin là đủ
  }, [targetMessage, fileToOpen, today.isSuccess, setParams, messages.length, olderPages.hasMore, olderPages.loading])

  const handleSend = (input: { text: string; mode: 'chat' | 'think' | 'research' | 'summary'; fileIds: number[] }) => {
    setDraft('')
    void send(input)
  }

  // Màn chat có conversation_id của phiên khác hôm nay: xem phiên cũ, chỉ đọc.
  const pastId = Number(params.get('phien')) || null
  if (pastId && today.data?.conversation?.id !== pastId) {
    return <PastConversation conversationId={pastId} onBack={() => setParams({}, { replace: true })} />
  }

  async function clearToday() {
    const id = today.data?.conversation?.id
    if (!id) return
    try {
      await deleteConversation(id)
      await queryClient.invalidateQueries({ queryKey: queryKeys.chat.today })
      toast.success('Đã xóa phiên hôm nay')
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-start justify-between gap-2 pb-3">
        <div>
          <h1 className="text-2xl font-bold">Trợ lý</h1>
          <p className="text-sm text-muted-foreground">{status.data ? `Tháng này ${formatUsd(status.data.month_usd)}` : ' '}</p>
        </div>
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" aria-label="Tìm" onClick={() => navigate('/tim')}>
            <Search className="size-5" />
          </Button>
          {messages.length > 0 && (
            <ConfirmDialog
              title="Xóa phiên hôm nay?"
              description="Toàn bộ tin nhắn hôm nay với trợ lý sẽ bị xóa. Chi tiêu, ghi chú đã ghi vẫn giữ nguyên."
              onConfirm={() => void clearToday()}
              trigger={
                <Button variant="ghost" size="icon" aria-label="Xóa phiên hôm nay">
                  <Trash2 className="size-5" />
                </Button>
              }
            />
          )}
        </div>
      </div>

      <div
        ref={listRef}
        onScroll={(e) => {
          const el = e.currentTarget
          atBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120
          if (el.scrollTop < 240) void loadOlder()
        }}
        className="-mx-4 flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain px-4 pb-4"
      >
        {olderPages.loading && (
          <div className="flex justify-center py-1 text-muted-foreground" role="status" aria-label="Đang tải tin cũ">
            <Loader2 className="size-4 animate-spin" />
          </div>
        )}
        <OfflineBanner />
        <UpdateBanner />
        {status.data?.over_monthly_warning && (
          <p className="flex items-start gap-2 rounded-xl border border-info/40 bg-info/10 p-3 text-sm">
            <Info className="mt-0.5 size-4 shrink-0 text-info" />
            Chi phí AI tháng này {formatUsd(status.data.month_usd)}, đã quá mức cảnh báo {formatUsd(status.data.monthly_warn_usd)}.
          </p>
        )}

        {today.isPending && <SkeletonList rows={3} />}
        {today.isError && <ErrorState error={today.error} onRetry={() => void today.refetch()} />}

        {today.isSuccess && messages.length === 0 && !turn && (
          <section className="flex flex-col items-center gap-3 rounded-2xl border bg-card px-5 py-8 text-center">
            <Bot className="size-10 text-primary" />
            <p className="text-sm text-muted-foreground">Nhắn một câu là em ghi, tra, nhắc. Bật Tìm web để hỏi tin mới, Nghĩ kỹ cho câu khó.</p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((text) => (
                <Button
                  key={text}
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  onClick={() =>
                    handleSend({
                      text,
                      mode: text.startsWith('Giá vàng') ? 'research' : 'chat',
                      fileIds: [],
                    })
                  }
                >
                  {text}
                </Button>
              ))}
            </div>
          </section>
        )}

        <div className="flex flex-col gap-4">
          {messages.map((message) => (
            <MessageBubble key={message.id} messageId={message.id} role={message.role} text={message.text} model={message.model} citations={message.citations} attachments={message.attachments}>
              {message.actions && (
                <ActionList actions={message.actions} hiddenFileIds={message.attachments?.map((a) => a.file_id)} pendingActions={today.data?.pending_actions} onChoice={(value) => handleSend({ text: value, mode: 'chat', fileIds: [] })} disabled={busy} />
              )}
            </MessageBubble>
          ))}

          {turn && (
            <>
              <MessageBubble role="user" text={turn.userText} attachments={turn.userMessage?.attachments ?? turn.attachments} />
              {turn.status === 'streaming' && !turn.text && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                  <Loader2 className="size-4 animate-spin" />
                  {turn.toolLabel ?? 'Em đang nghĩ...'}
                </div>
              )}
              {turn.text && (
                <MessageBubble role="assistant" text={turn.text} model={turn.assistant?.model} citations={turn.assistant?.citations}>
                  {turn.status === 'streaming' && turn.toolLabel && (
                    <span className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="size-3 animate-spin" />
                      {turn.toolLabel}
                    </span>
                  )}
                  <ActionList actions={turn.actions} onChoice={(value) => handleSend({ text: value, mode: 'chat', fileIds: [] })} disabled={busy} />
                </MessageBubble>
              )}
              {turn.status === 'error' && turn.error && (
                <div className="flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm">
                  <TriangleAlert className="mt-0.5 size-4 shrink-0 text-destructive" />
                  <span className="min-w-0 flex-1">{turn.error.message}</span>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setDraft('')
                      retry()
                    }}
                  >
                    <RefreshCw className="size-4" />
                    Gửi lại
                  </Button>
                  <Button size="sm" variant="ghost" onClick={dismiss}>
                    Bỏ
                  </Button>
                </div>
              )}
            </>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <Composer busy={busy} draft={draft} onDraftChange={setDraft} onSend={handleSend} />
    </div>
  )
}
