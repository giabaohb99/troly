import { useEffect, useMemo, useState } from 'react'
import { FileText, Loader2, MessageSquarePlus, Send, Share2, X } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { ShareIn, sharedFileToFile, sharedFileUrl, type SharedPayload } from '@/core/native/share-in'
import { createSession, listSessions } from '@/modules/chat/api/chat-api'
import { uploadFile } from '@/modules/chat/api/upload-api'
import { defaultShareTarget, sessionTitle, sortSessions } from '@/modules/chat/utils/sessions'
import { queryKeys } from '@/shared/constants/query-keys'
import { Button } from '@/shared/ui/button'
import { Textarea } from '@/shared/ui/textarea'
import { fileKindLabel, formatFileSize, isImageFile, truncateMiddle } from '@/shared/utils/open-file'
import { formatWhen } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

const NEW = 'moi'

// Màn chia sẻ vào Trợ lý (QĐ-51 bước 2): xem trước chữ và tệp, ghi thêm lời nhắn, chọn phiên (mặc định phiên hoạt
// động gần nhất) hoặc phiên mới, Gửi thì tải tệp lên rồi mở phiên và gửi ngay.
export function SharePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const payload = (useLocation().state ?? null) as SharedPayload | null
  const [text, setText] = useState(payload?.text ?? '')
  const [target, setTarget] = useState<number | typeof NEW | null>(null)
  const [sending, setSending] = useState(false)
  // Khóa riêng: ngăn kéo Các phiên lưu dạng nhiều trang dưới queryKeys.chat.sessions(q).
  const sessions = useQuery({ queryKey: [...queryKeys.chat.sessionsAll, 'chia-se'], queryFn: () => listSessions('', null), enabled: !!payload })
  const items = useMemo(() => sortSessions(sessions.data?.items ?? []).slice(0, 20), [sessions.data])

  // Chọn sẵn phiên hoạt động gần nhất khi có danh sách; chưa có phiên nào thì phiên mới.
  useEffect(() => {
    if (target === null && sessions.isSuccess) setTarget(defaultShareTarget(sessions.data.items) ?? NEW)
  }, [target, sessions.isSuccess, sessions.data])

  if (!payload) return <Navigate to="/" replace />
  const files = payload.files

  const cancel = () => {
    void ShareIn.cleanup().catch(() => null)
    navigate('/', { replace: true })
  }

  async function send() {
    if (sending || target === null) return
    if (!text.trim() && files.length === 0) {
      toast.error('Không có gì để gửi.')
      return
    }
    setSending(true)
    try {
      const fileIds: number[] = []
      for (const f of files) fileIds.push((await uploadFile(await sharedFileToFile(f))).id)
      const id = target === NEW ? (await createSession()).id : target
      void queryClient.invalidateQueries({ queryKey: queryKeys.chat.sessionsAll })
      void ShareIn.cleanup().catch(() => null)
      navigate(`/?phien=${id}`, { replace: true, state: { autoSend: { text: text.trim(), fileIds } } })
    } catch (error) {
      toast.error(getErrorMessage(error))
      setSending(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 pb-8">
      <div className="flex items-center gap-2">
        <Button size="icon" variant="ghost" aria-label="Bỏ chia sẻ" onClick={cancel}>
          <X className="size-5" />
        </Button>
        <h1 className="flex min-w-0 flex-1 items-center gap-2 text-lg font-bold">
          <Share2 className="size-5 text-primary" />
          Chia sẻ vào Trợ lý
        </h1>
      </div>

      {files.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {files.map((f) => (
            <div key={f.path} className="shrink-0">
              {isImageFile(f.mime, f.name) ? (
                <img src={sharedFileUrl(f)} alt={f.name} className="size-20 rounded-xl object-cover" />
              ) : (
                <div className="flex h-20 w-44 items-center gap-2 rounded-xl border bg-card px-3">
                  <FileText className="size-5 shrink-0 text-primary" />
                  <span className="min-w-0">
                    <span className="block text-xs font-medium" title={f.name}>
                      {truncateMiddle(f.name, 22)}
                    </span>
                    <span className="block text-[11px] text-muted-foreground">{[fileKindLabel(f.mime, f.name), formatFileSize(f.size)].filter(Boolean).join(' · ')}</span>
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {payload.skipped > 0 && <p className="text-xs text-warning">Bỏ qua {payload.skipped} tệp: loại chưa đọc được, quá 25 MB hoặc quá 4 tệp.</p>}

      <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} maxLength={4000} placeholder="Nhắn kèm, ví dụ: tóm tắt giúp em, lưu vào ghi chú..." aria-label="Nhắn kèm" />

      <section className="flex flex-col gap-1.5">
        <h2 className="text-sm font-semibold text-muted-foreground">Gửi vào phiên</h2>
        <div className="flex flex-col gap-1" role="radiogroup" aria-label="Gửi vào phiên">
          <button
            type="button"
            role="radio"
            aria-checked={target === NEW}
            onClick={() => setTarget(NEW)}
            className={cn('flex items-center gap-2 rounded-xl border px-3 py-2.5 text-left text-sm', target === NEW && 'border-primary bg-primary/10 font-medium')}
          >
            <MessageSquarePlus className="size-4 text-primary" />
            Phiên mới
          </button>
          {sessions.isPending && <Loader2 className="mx-auto my-2 size-4 animate-spin text-muted-foreground" />}
          {items.map((s) => (
            <button
              key={s.id}
              type="button"
              role="radio"
              aria-checked={target === s.id}
              onClick={() => setTarget(s.id)}
              className={cn('flex items-center gap-2 rounded-xl border px-3 py-2.5 text-left text-sm', target === s.id && 'border-primary bg-primary/10 font-medium')}
            >
              <span className="min-w-0 flex-1 truncate">{sessionTitle(s)}</span>
              {s.last_message_at && <span className="shrink-0 text-[11px] text-muted-foreground">{formatWhen(s.last_message_at)}</span>}
            </button>
          ))}
        </div>
      </section>

      <Button disabled={sending || target === null} onClick={() => void send()}>
        {sending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
        {sending ? 'Đang gửi...' : 'Gửi'}
      </Button>
    </div>
  )
}
