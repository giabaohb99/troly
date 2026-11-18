import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Brain, Globe, Loader2, Mic, Paperclip, Send, Square, X } from 'lucide-react'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { ACCEPTED_FILES, uploadFile, type UploadedFile } from '@/modules/chat/api/upload-api'
import type { ChatMode } from '@/modules/chat/types/chat'
import { useSpeechRecognition } from '@/shared/voice/use-speech-recognition'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/utils/cn'

export const MAX_MESSAGE_CHARS = 4000
const MAX_FILES = 4

interface ComposerProps {
  busy: boolean
  draft: string
  onDraftChange: (text: string) => void
  onSend: (input: { text: string; mode: ChatMode; fileIds: number[] }) => void
}

interface PendingFile {
  key: string
  name: string
  uploaded: UploadedFile | null
}

// Ô nhập chat: Nghĩ kỹ (mode think, Sonnet), Tìm web (mode research), đính tệp, micro (31 mục 3.5).
// Hai nút chế độ tự tắt sau khi gửi.
export function Composer({ busy, draft, onDraftChange, onSend }: ComposerProps) {
  const [mode, setMode] = useState<ChatMode>('chat')
  const [files, setFiles] = useState<PendingFile[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const uploading = files.some((f) => !f.uploaded)
  const tooLong = draft.length > MAX_MESSAGE_CHARS

  const submit = useCallback(
    (text: string) => {
      const content = text.trim()
      if ((!content && files.length === 0) || busy || uploading || content.length > MAX_MESSAGE_CHARS) return
      onSend({ text: content, mode, fileIds: files.flatMap((f) => (f.uploaded ? [f.uploaded.id] : [])) })
      setMode('chat')
      setFiles([])
    },
    [busy, files, mode, onSend, uploading],
  )

  const handleSpeechError = useCallback((message: string) => toast.error(message), [])
  const speech = useSpeechRecognition({ onFinal: submit, onError: handleSpeechError })

  // Ô nhập cao theo chữ, tối đa 6 dòng.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [draft])

  async function pickFiles(list: FileList | null) {
    if (!list) return
    const chosen = Array.from(list).slice(0, MAX_FILES - files.length)
    for (const file of chosen) {
      const key = crypto.randomUUID()
      setFiles((prev) => [...prev, { key, name: file.name, uploaded: null }])
      try {
        const uploaded = await uploadFile(file)
        setFiles((prev) => prev.map((f) => (f.key === key ? { ...f, uploaded } : f)))
      } catch (error) {
        setFiles((prev) => prev.filter((f) => f.key !== key))
        toast.error(getErrorMessage(error))
      }
    }
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    submit(draft)
  }

  // Trên máy tính: Enter gửi, Shift+Enter xuống dòng. Trên điện thoại bàn phím ảo không gửi Enter kiểu này.
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && window.matchMedia('(pointer: fine)').matches) {
      event.preventDefault()
      submit(draft)
    }
  }

  const toggleMode = (next: ChatMode) => setMode((current) => (current === next ? 'chat' : next))

  return (
    <form onSubmit={handleSubmit} className="-mx-4 shrink-0 border-t bg-background px-4 py-2">
      <div className="mx-auto flex max-w-lg flex-col gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            aria-pressed={mode === 'think'}
            onClick={() => toggleMode('think')}
            className={cn('inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs', mode === 'think' && 'border-primary bg-primary/15 text-primary')}
          >
            <Brain className="size-3.5" />
            Nghĩ kỹ
          </button>
          <button
            type="button"
            aria-pressed={mode === 'research'}
            onClick={() => toggleMode('research')}
            className={cn('inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs', mode === 'research' && 'border-primary bg-primary/15 text-primary')}
          >
            <Globe className="size-3.5" />
            Tìm web
          </button>
          {files.map((file) => (
            <span key={file.key} className="inline-flex max-w-[10rem] items-center gap-1 rounded-full bg-secondary px-2 py-1 text-xs">
              {file.uploaded ? null : <Loader2 className="size-3 animate-spin" />}
              <span className="truncate">{file.name}</span>
              <button type="button" aria-label={`Bỏ tệp ${file.name}`} onClick={() => setFiles((prev) => prev.filter((f) => f.key !== file.key))}>
                <X className="size-3" />
              </button>
            </span>
          ))}
          {draft.length > MAX_MESSAGE_CHARS - 200 && (
            <span className={cn('ml-auto text-xs', tooLong ? 'text-destructive' : 'text-muted-foreground')}>
              {draft.length}/{MAX_MESSAGE_CHARS}
            </span>
          )}
        </div>
        <div className="flex items-end gap-2">
          <input ref={fileInputRef} type="file" accept={ACCEPTED_FILES} multiple hidden onChange={(e) => void pickFiles(e.target.files).finally(() => (e.target.value = ''))} />
          <Button type="button" size="icon" variant="ghost" className="size-11 shrink-0 rounded-full" aria-label="Đính tệp" disabled={files.length >= MAX_FILES} onClick={() => fileInputRef.current?.click()}>
            <Paperclip className="size-5" />
          </Button>
          {speech.supported && (
            <Button
              type="button"
              size="icon"
              variant={speech.listening ? 'destructive' : 'secondary'}
              className="size-11 shrink-0 rounded-full"
              aria-label={speech.listening ? 'Dừng nghe' : 'Nói với trợ lý'}
              disabled={busy}
              onClick={() => (speech.listening ? speech.stop() : speech.start())}
            >
              {speech.listening ? <Square className="size-4" /> : <Mic className="size-5" />}
            </Button>
          )}
          <textarea
            ref={textareaRef}
            rows={1}
            value={speech.listening ? speech.interim : draft}
            onChange={(e) => onDraftChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={speech.listening ? 'Đang nghe...' : mode === 'research' ? 'Hỏi để em tìm trên web' : 'Nhắn cho trợ lý'}
            disabled={speech.listening}
            aria-label="Tin nhắn"
            className="min-h-11 min-w-0 flex-1 resize-none rounded-3xl bg-secondary px-4 py-2.5 text-base outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring"
          />
          <Button
            type="submit"
            size="icon"
            className="size-11 shrink-0 rounded-full"
            aria-label="Gửi"
            disabled={busy || uploading || tooLong || (!draft.trim() && files.length === 0)}
          >
            {busy ? <Loader2 className="size-5 animate-spin" /> : <Send className="size-5" />}
          </Button>
        </div>
      </div>
    </form>
  )
}
