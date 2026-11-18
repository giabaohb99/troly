import { useEffect, useRef, useState } from 'react'
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
  const messages = today.data?.messages ?? []

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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, turn?.text, turn?.actions.length, turn?.status])

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
    <div className="flex flex-col gap-4 pb-32">
      <div className="flex items-start justify-between gap-2">
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
              <Button key={text} variant="secondary" size="sm" disabled={busy} onClick={() => handleSend({ text, mode: text.startsWith('Giá vàng') ? 'research' : 'chat', fileIds: [] })}>
                {text}
              </Button>
            ))}
          </div>
        </section>
      )}

      <div className="flex flex-col gap-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} role={message.role} text={message.text} model={message.model} citations={message.citations} attachments={message.attachments}>
            {message.actions && <ActionList actions={message.actions} pendingActions={today.data?.pending_actions} onChoice={(value) => handleSend({ text: value, mode: 'chat', fileIds: [] })} disabled={busy} />}
          </MessageBubble>
        ))}

        {turn && (
          <>
            <MessageBubble role="user" text={turn.userText} />
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
                <Button size="sm" variant="secondary" onClick={() => { setDraft(''); retry() }}>
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
        {/* Chừa chỗ cho ô nhập và thanh dưới cố định khi tự cuộn xuống cuối. */}
        <div ref={bottomRef} className="scroll-mb-[calc(11rem+env(safe-area-inset-bottom))]" />
      </div>

      <Composer busy={busy} draft={draft} onDraftChange={setDraft} onSend={handleSend} />
    </div>
  )
}
