import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Info, Loader2, Menu, MoreVertical, RefreshCw, Search, TriangleAlert } from 'lucide-react'
import { AppMark } from '@/shared/components/app-mark'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError, getErrorMessage } from '@/core/api/api-error'
import { createSession } from '@/modules/chat/api/chat-api'
import { ActionList } from '@/modules/chat/components/action-list'
import { Composer } from '@/modules/chat/components/composer'
import type { SharedPayload } from '@/core/native/share-in'
import { MessageBubble } from '@/modules/chat/components/message-bubble'
import { RenameSessionDialog, SessionActionsDialog, useSessionMutations } from '@/modules/chat/components/session-actions'
import { SessionsDrawer } from '@/modules/chat/components/sessions-drawer'
import { sessionTitle, rememberOpenSession } from '@/modules/chat/utils/sessions'
import { chatViewKey, useChatStatus, useChatTurn, useChatView } from '@/modules/chat/hooks/use-chat'
import { queryKeys } from '@/shared/constants/query-keys'
import { ErrorState } from '@/shared/components/error-state'
import { OfflineBanner } from '@/shared/components/offline-banner'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { UpdateBanner } from '@/shared/components/update-banner'
import { Button } from '@/shared/ui/button'
import { formatUsd } from '@/shared/utils/format'
import { useOpenFile } from '@/shared/hooks/use-open-file'
import { useOlderMessages } from '@/modules/chat/hooks/use-older-messages'
import { mergeOlder } from '@/modules/chat/utils/older-messages'
import { Alarm } from '@/core/native/alarm'
import { TTS_NO_VI, Voice } from '@/core/native/voice'
import { toSpeakable } from '@/shared/voice/speakable'
import { useReadReplies } from '@/shared/voice/voice-prefs'

// Mở từ thông báo tới tin cũ: tải thêm tối đa chừng này trang (50 tin mỗi trang) để tìm.
const MAX_SEEK_PAGES = 20

const SUGGESTIONS = ['cơm trưa 45k', 'Tháng này tiêu bao nhiêu rồi?', 'Tìm ghi chú về hợp đồng nhà', 'Giá vàng hôm nay']

// Màn chính (31 mục 3.5, QĐ-51): một phiên chat đặt tên. Không có ?phien= là phiên hoạt động gần nhất (/chat/today);
// có là phiên đó, chat tiếp được (mở từ Các phiên, Tìm, thông báo trợ lý trả lời). Đổi phiên thì dựng lại màn.
export function ChatPage() {
  const [params] = useSearchParams()
  const sessionId = Number(params.get('phien')) || null
  return <ChatView key={sessionId ?? 'gan-nhat'} sessionId={sessionId} />
}

function ChatView({ sessionId }: { sessionId: number | null }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const today = useChatView(sessionId)
  const status = useChatStatus()
  const { turn, send, retry, dismiss, busy } = useChatTurn(chatViewKey(sessionId), today.data?.conversation?.id ?? sessionId)
  const [params, setParams] = useSearchParams()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const session = today.data?.conversation ?? null
  const openSession = (id: number | null) => {
    setDrawerOpen(false)
    if (id === (session?.id ?? null) && sessionId !== null) return
    navigate(id ? `/?phien=${id}` : '/', { replace: true })
  }
  const newSession = useMutation({
    mutationFn: () => createSession(),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.chat.sessionsAll })
      openSession(created.id)
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  // Xóa phiên đang mở: về phiên hoạt động gần nhất.
  const afterDelete = (id: number) => {
    if (id === session?.id) navigate('/', { replace: true })
  }
  const { update } = useSessionMutations(afterDelete)
  // Phiên không còn (máy chủ dọn phiên rỗng sau 1 ngày, hoặc đã xóa ở máy khác): về phiên gần nhất thay vì kẹt ở lỗi.
  const missing = sessionId !== null && today.error instanceof ApiError && today.error.status === 404
  useEffect(() => {
    if (!missing) return
    toast.info('Phiên này không còn.')
    navigate('/', { replace: true })
  }, [missing, navigate])

  // Chia sẻ từ app khác (QĐ-51 bước 2): vào thẳng ô nhập của phiên đang mở; nhận xong thì xóa khỏi lịch sử điều hướng.
  const location = useLocation()
  const incoming = (location.state as { shared?: SharedPayload } | null)?.shared ?? null
  const clearIncoming = () => navigate(`${location.pathname}${location.search}`, { replace: true, state: null })
  useEffect(() => {
    if (session?.id) rememberOpenSession(session.id)
  }, [session?.id])
  const [draft, setDraft] = useState(() => params.get('hoi') ?? '')
  const bottomRef = useRef<HTMLDivElement>(null)
  const openFile = useOpenFile()
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
    if (fileToOpen) void openFile(fileToOpen)
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

  // Hỏi bằng giọng thì đọc to câu trả lời (1.0.6, công tắc ở Cài đặt → Thông báo, mục Giọng nói). Chạm màn hình hoặc
  // bấm micro thì dừng đọc.
  const readReplies = useReadReplies()
  const voiceTurnRef = useRef(false)
  const speakingRef = useRef(false)
  const stopSpeaking = () => {
    if (!speakingRef.current) return
    speakingRef.current = false
    void Voice.stopSpeaking().catch(() => null)
  }
  useEffect(() => {
    const handle = Voice.addListener('speakEnd', () => {
      speakingRef.current = false
    })
    return () => {
      void handle.then((h) => h.remove())
      void Voice.stopSpeaking().catch(() => null)
    }
  }, [])
  useEffect(() => {
    if (turn?.status !== 'done' || !voiceTurnRef.current) return
    voiceTurnRef.current = false
    if (!readReplies) return
    const text = toSpeakable(turn.assistant?.text ?? turn.text)
    if (!text) return
    speakingRef.current = true
    Voice.speak({ text }).catch((error: { code?: string; message?: string }) => {
      speakingRef.current = false
      if (error?.code === TTS_NO_VI) {
        toast.error(error.message || 'Máy chưa có giọng đọc tiếng Việt.', { action: { label: 'Mở cài đặt', onClick: () => void Voice.openTtsSettings() } })
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ chạy khi lượt chuyển sang xong
  }, [turn?.status])

  const handleSend = (input: { text: string; mode: 'chat' | 'think' | 'research' | 'summary'; fileIds: number[]; voice?: boolean; refs?: number[] }) => {
    setDraft('')
    stopSpeaking()
    voiceTurnRef.current = !!input.voice
    void send({ text: input.text, mode: input.mode, fileIds: input.fileIds, refs: input.refs })
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col" onPointerDown={stopSpeaking}>
      <div className="flex shrink-0 items-start gap-1 pb-3">
        <Button variant="ghost" size="icon" className="-ml-2 shrink-0" aria-label="Các phiên" onClick={() => setDrawerOpen(true)}>
          <Menu className="size-5" />
        </Button>
        <div className="min-w-0 flex-1">
          {/* Tên phiên; bấm để đổi tên (phiên chưa có thì chưa đổi được, gửi tin đầu máy chủ tự đặt tên). */}
          <button type="button" className="block max-w-full truncate text-left text-xl font-bold" disabled={!session} onClick={() => setRenaming(true)} title="Bấm để đổi tên phiên">
            {session ? sessionTitle(session) : 'Trợ lý'}
          </button>
          <p className="text-sm text-muted-foreground">{status.data ? `Tháng này ${formatUsd(status.data.month_usd)}` : ' '}</p>
        </div>
        <div className="flex shrink-0 gap-1">
          <Button variant="ghost" size="icon" aria-label="Tìm" onClick={() => navigate('/tim')}>
            <Search className="size-5" />
          </Button>
          {session && (
            <Button variant="ghost" size="icon" aria-label="Menu phiên" onClick={() => setMenuOpen(true)}>
              <MoreVertical className="size-5" />
            </Button>
          )}
        </div>
      </div>
      <SessionsDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        currentId={session?.id ?? null}
        onSelect={(id) => openSession(id)}
        onNew={() => newSession.mutate()}
        creating={newSession.isPending}
        onDeleted={afterDelete}
      />
      <SessionActionsDialog session={menuOpen ? session : null} onClose={() => setMenuOpen(false)} onDeleted={afterDelete} />
      <RenameSessionDialog
        session={session}
        open={renaming}
        onOpenChange={setRenaming}
        saving={update.isPending}
        onSave={(title) => session && update.mutate({ id: session.id, patch: { title } }, { onSuccess: () => setRenaming(false) })}
      />

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
        {today.isError && !missing && <ErrorState error={today.error} onRetry={() => void today.refetch()} />}

        {today.isSuccess && messages.length === 0 && !turn && (
          <section className="flex flex-col items-center gap-3 rounded-2xl border bg-card px-5 py-8 text-center">
            <AppMark className="size-14" />
            <p className="text-sm text-muted-foreground">Nhắn một câu là em ghi, tra, nhắc. Gõ @ để gọi thêm một đoạn chat khác vào.</p>
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
              {/* Máy chủ che khóa API trong tin trước khi lưu (QĐ-46): có bản của máy chủ thì hiện bản đó thay chữ vừa gõ. */}
              <MessageBubble role="user" text={turn.userMessage?.text ?? turn.userText} attachments={turn.userMessage?.attachments ?? turn.attachments} />
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

      <Composer busy={busy} draft={draft} onDraftChange={setDraft} onSend={handleSend} incoming={incoming} onIncomingDone={clearIncoming} sessionId={session?.id ?? null} />
    </div>
  )
}
