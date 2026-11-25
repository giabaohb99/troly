import { useEffect, useLayoutEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { ChevronLeft, History, Loader2, MoreVertical, Paperclip, RotateCcw, Send, Users, X } from 'lucide-react'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { listMessages, markConversation } from '@/modules/inbox/api/inbox-api'
import { sendZaloMessage, syncZaloConversation, ZALO_MAX_FILES } from '@/modules/inbox/api/zalo-api'
import { PendingFileChip, ZaloMediaView } from '@/modules/inbox/components/zalo-media'
import type { InboxMessage } from '@/modules/inbox/types/inbox'
import { groupByDay, isZaloGroupKey, needsZaloLogin, reconcilePending, zaloSendErrorText, type PendingSend } from '@/modules/inbox/utils/zalo'
import { uploadFile } from '@/shared/api/upload-api'
import { ErrorState } from '@/shared/components/error-state'
import { RichText } from '@/shared/components/rich-text'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { queryKeys } from '@/shared/constants/query-keys'
import { Button } from '@/shared/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { formatDayTitle, formatTime } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

// Một bong bóng tin Zalo: tin người khác bên trái (nhóm có tên người gửi), tin của mình bên phải; trích dẫn chỉ hiển
// thị; tin thu hồi in nghiêng; link, số, email bấm được.
function Bubble({ m, group, onEmail }: { m: InboxMessage; group: boolean; onEmail: (email: string) => void }) {
  const self = !!m.is_self
  const recalled = !!m.recalled_at
  return (
    <div className={cn('flex flex-col gap-0.5', self ? 'items-end' : 'items-start')}>
      {group && !self && m.sender && <span className="px-2 text-xs font-medium text-muted-foreground">{m.sender}</span>}
      <div
        className={cn(
          'flex max-w-[82%] flex-col gap-1.5 rounded-2xl px-3.5 py-2 text-[15px] leading-relaxed break-words whitespace-pre-wrap',
          self ? 'rounded-tr-md bg-primary text-primary-foreground' : 'rounded-tl-md border bg-card',
        )}
      >
        {m.quote && !recalled && (
          <span className={cn('block border-l-2 pl-2 text-xs opacity-80', self ? 'border-primary-foreground/60' : 'border-primary/60')}>{m.quote.text || 'Tin được trích dẫn'}</span>
        )}
        {recalled ? (
          <span className="italic opacity-80">(Tin đã thu hồi)</span>
        ) : (
          <>
            {m.media?.map((media, i) => <ZaloMediaView key={`${m.id}-${i}`} media={media} />)}
            {m.text && <RichText text={m.text} compactLinks onEmail={onEmail} />}
          </>
        )}
      </div>
      <span className="px-2 text-[11px] text-muted-foreground">{formatTime(m.posted_at)}</span>
    </div>
  )
}

// Khung chat Zalo (QĐ-52) cho hội thoại có khóa đầy đủ của bridge: bong bóng kiểu Zalo, gộp theo ngày, đứng ở tin cuối;
// gửi chữ, ảnh, tệp (người dùng tự gõ thì gửi thẳng; bot gửi thay luôn qua thẻ duyệt ở chat). Tin vừa gửi hiện tạm
// tới khi bridge báo lại.
export function ZaloChatPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const key = useParams().conversationKey ?? ''
  const group = isZaloGroupKey(key)
  const [pending, setPending] = useState<PendingSend[]>([])
  const [text, setText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [loginNeeded, setLoginNeeded] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const sendingRef = useRef(false)
  const lastInputRef = useRef(new Map<string, { text: string; files: File[] }>())

  const messages = useInfiniteQuery({
    queryKey: queryKeys.inbox.messages(key),
    queryFn: ({ pageParam }) => listMessages(key, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    // Đang chờ bridge báo lại tin vừa gửi: hỏi 3 giây; bình thường 15 giây để thấy tin mới.
    refetchInterval: () => (pending.some((p) => p.status === 'sent') ? 3_000 : 15_000),
  })
  const items = useMemo(() => (messages.data?.pages ?? []).flatMap((p) => p.items), [messages.data])
  const groups = useMemo(() => groupByDay(items), [items])
  const title = items.find((m) => m.conversation_title)?.conversation_title ?? items.find((m) => !m.is_self && m.sender)?.sender ?? 'Zalo'

  // Bridge báo lại tin của mình thì bỏ bản tạm.
  useEffect(() => {
    setPending((prev) => {
      const next = reconcilePending(prev, items)
      return next.length === prev.length ? prev : next
    })
  }, [items])

  // Mở là đã xem.
  const markedRef = useRef(false)
  useEffect(() => {
    if (markedRef.current || !items.some((m) => m.status === 'new')) return
    markedRef.current = true
    void markConversation(key, 'seen').then(() => queryClient.invalidateQueries({ queryKey: queryKeys.inbox.all }))
  }, [items, key, queryClient])

  // Đứng ở tin cuối khi mở và khi có tin mới, tin tạm.
  const lastId = items[items.length - 1]?.id
  useLayoutEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [lastId, pending.length])

  const sync = useMutation({
    mutationFn: () => syncZaloConversation(key),
    onSuccess: (r) => {
      setMenuOpen(false)
      toast.success(r.mode === 'group_history' ? `Đã lấy ${r.saved ?? 0} tin cũ của nhóm` : 'Zalo không giữ lịch sử chat một-một; tin mới sẽ về từ giờ.')
      void queryClient.invalidateQueries({ queryKey: queryKeys.inbox.messages(key) })
    },
    onError: (error) => toast.error(zaloSendErrorText(error)),
  })

  async function deliver(clientRef: string, body: string, picked: File[]) {
    try {
      const fileIds: number[] = []
      for (const f of picked) fileIds.push((await uploadFile(f, 'other')).id)
      await sendZaloMessage({ conversation_key: key, text: body || undefined, file_ids: fileIds.length ? fileIds : undefined, client_ref: clientRef })
      setPending((prev) => prev.map((p) => (p.clientRef === clientRef ? { ...p, status: 'sent' } : p)))
      lastInputRef.current.delete(clientRef)
      void queryClient.invalidateQueries({ queryKey: queryKeys.inbox.messages(key) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.inbox.all })
    } catch (error) {
      if (needsZaloLogin(error)) setLoginNeeded(true)
      setPending((prev) => prev.map((p) => (p.clientRef === clientRef ? { ...p, status: 'failed', error: zaloSendErrorText(error) } : p)))
    }
  }

  async function submit(e?: FormEvent) {
    e?.preventDefault()
    const body = text.trim()
    if ((!body && files.length === 0) || sendingRef.current) return
    sendingRef.current = true
    const clientRef = crypto.randomUUID()
    const picked = files
    lastInputRef.current.set(clientRef, { text: body, files: picked })
    setPending((prev) => [...prev, { clientRef, text: body, fileNames: picked.map((f) => f.name), createdAt: Date.now(), status: 'sending' }])
    setText('')
    setFiles([])
    sendingRef.current = false
    await deliver(clientRef, body, picked)
  }

  function retry(p: PendingSend) {
    const input = lastInputRef.current.get(p.clientRef)
    setPending((prev) => prev.map((x) => (x.clientRef === p.clientRef ? { ...x, status: 'sending', error: undefined, createdAt: Date.now() } : x)))
    void deliver(p.clientRef, input?.text ?? p.text, input?.files ?? [])
  }

  const onEmail = (email: string) => navigate('/hop-tin/email/soan', { state: { to: [email] } })

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center gap-1 pb-2">
        <Button size="icon" variant="ghost" aria-label="Quay lại" onClick={() => navigate('/hop-tin?loai=zalo')}>
          <ChevronLeft className="size-5" />
        </Button>
        <span className="inline-flex shrink-0 rounded-md bg-app-2/20 px-1.5 py-0.5 text-[11px] font-semibold text-app-2">Zalo</span>
        {group && <Users className="size-4 shrink-0 text-muted-foreground" aria-label="Nhóm" />}
        <h1 className="min-w-0 flex-1 truncate text-lg font-semibold">{title}</h1>
        <Button size="icon" variant="ghost" aria-label="Menu hội thoại" onClick={() => setMenuOpen(true)}>
          <MoreVertical className="size-5" />
        </Button>
      </div>

      {loginNeeded && (
        <div className="mb-2 flex items-center gap-2 rounded-xl border border-warning/40 bg-warning/10 px-3 py-2 text-sm">
          <span className="min-w-0 flex-1">Zalo chưa đăng nhập nên chưa gửi được.</span>
          <Button size="sm" variant="secondary" asChild>
            <Link to="/cai-dat/zalo">Quét mã</Link>
          </Button>
        </div>
      )}

      <div ref={listRef} className="-mx-4 flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto overscroll-contain px-4 pb-3">
        {messages.hasNextPage && (
          <Button variant="ghost" size="sm" className="self-center" disabled={messages.isFetchingNextPage} onClick={() => void messages.fetchNextPage()}>
            {messages.isFetchingNextPage && <Loader2 className="size-4 animate-spin" />}
            Xem tin cũ hơn
          </Button>
        )}
        {messages.isPending && <SkeletonList rows={4} />}
        {messages.isError && <ErrorState error={messages.error} onRetry={() => void messages.refetch()} />}
        {messages.isSuccess && items.length === 0 && pending.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">Chưa có tin. {group ? 'Bấm menu, Lấy tin cũ của nhóm.' : 'Tin một-một chỉ có từ lúc đăng nhập Zalo trong app.'}</p>
        )}
        {groups.map((g) => (
          <div key={g.day} className="flex flex-col gap-3">
            <p className="self-center rounded-full bg-muted px-3 py-0.5 text-[11px] text-muted-foreground">{formatDayTitle(g.day)}</p>
            {g.items.map((m) => (
              <Bubble key={m.id} m={m} group={group} onEmail={onEmail} />
            ))}
          </div>
        ))}
        {pending.map((p) => (
          <div key={p.clientRef} className="flex flex-col items-end gap-0.5">
            <div className={cn('flex max-w-[82%] flex-col gap-1 rounded-2xl rounded-tr-md px-3.5 py-2 text-[15px] whitespace-pre-wrap', p.status === 'failed' ? 'border border-destructive/50 bg-destructive/5' : 'bg-primary/70 text-primary-foreground')}>
              {p.fileNames.map((n) => (
                <PendingFileChip key={n} name={n} />
              ))}
              {p.text}
            </div>
            {p.status === 'failed' ? (
              <span className="flex items-center gap-2 px-2 text-[11px] text-destructive">
                {p.error}
                <button type="button" className="inline-flex items-center gap-1 font-medium underline" onClick={() => retry(p)}>
                  <RotateCcw className="size-3" />
                  Gửi lại
                </button>
              </span>
            ) : (
              <span className="flex items-center gap-1 px-2 text-[11px] text-muted-foreground">
                <Loader2 className="size-3 animate-spin" />
                {p.status === 'sending' ? 'Đang gửi' : 'Đã gửi, chờ Zalo báo lại'}
              </span>
            )}
          </div>
        ))}
      </div>

      <form onSubmit={(e) => void submit(e)} className="-mx-4 shrink-0 border-t bg-background px-4 py-2">
        {files.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {files.map((f, i) => (
              <span key={`${f.name}-${i}`} className="flex items-center gap-1 rounded-full border bg-card px-2 py-0.5 text-xs">
                <PendingFileChip name={f.name} />
                <button type="button" aria-label={`Bỏ ${f.name}`} onClick={() => setFiles(files.filter((_, j) => j !== i))}>
                  <X className="size-3" />
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="flex items-end gap-2">
          <input
            ref={fileRef}
            type="file"
            multiple
            hidden
            accept="image/*,video/*,application/pdf,.docx,.xlsx,.txt,.md"
            onChange={(e) => {
              const picked = Array.from(e.target.files ?? [])
              if (files.length + picked.length > ZALO_MAX_FILES) toast.error(`Gửi tối đa ${ZALO_MAX_FILES} tệp một lần.`)
              setFiles([...files, ...picked].slice(0, ZALO_MAX_FILES))
              e.target.value = ''
            }}
          />
          <Button type="button" size="icon" variant="ghost" className="size-11 shrink-0 rounded-full" aria-label="Đính ảnh, tệp" disabled={files.length >= ZALO_MAX_FILES} onClick={() => fileRef.current?.click()}>
            <Paperclip className="size-5" />
          </Button>
          <textarea
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Nhắn Zalo"
            maxLength={2000}
            aria-label="Tin Zalo"
            className="max-h-32 min-h-11 min-w-0 flex-1 resize-none rounded-3xl bg-secondary px-4 py-2.5 text-base outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring"
          />
          <Button type="submit" size="icon" className="size-11 shrink-0 rounded-full" aria-label="Gửi Zalo" disabled={!text.trim() && files.length === 0}>
            <Send className="size-5" />
          </Button>
        </div>
      </form>

      <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="truncate">{title}</DialogTitle>
            <DialogDescription className="sr-only">Việc với hội thoại Zalo</DialogDescription>
          </DialogHeader>
          <Button variant="ghost" className="justify-start" disabled={sync.isPending} onClick={() => sync.mutate()}>
            {sync.isPending ? <Loader2 className="size-4 animate-spin" /> : <History className="size-4" />}
            {group ? 'Lấy tin cũ của nhóm' : 'Lấy tin cũ'}
          </Button>
          <Button
            variant="ghost"
            className="justify-start"
            onClick={() => {
              setMenuOpen(false)
              void markConversation(key, 'done')
                .then(() => queryClient.invalidateQueries({ queryKey: queryKeys.inbox.all }))
                .then(() => toast.success('Đã đánh dấu xử lý'))
                .catch((error) => toast.error(getErrorMessage(error)))
            }}
          >
            Đánh dấu đã xử lý
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  )
}
