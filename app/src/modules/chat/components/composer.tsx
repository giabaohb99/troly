import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Brain, FileText, Globe, Loader2, Mic, Paperclip, Send, Square, X } from 'lucide-react'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { ACCEPTED_FILES, uploadFile, type UploadedFile } from '@/modules/chat/api/upload-api'
import type { ChatMode } from '@/modules/chat/types/chat'
import { Voice } from '@/core/native/voice'
import { useSpeechRecognition } from '@/shared/voice/use-speech-recognition'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/utils/cn'
import { fileKindLabel, formatFileSize, isImageFile, truncateMiddle } from '@/shared/utils/open-file'

export const MAX_MESSAGE_CHARS = 4000
const MAX_FILES = 4

interface ComposerProps {
  busy: boolean
  draft: string
  onDraftChange: (text: string) => void
  // voice: tin nói bằng micro (màn chat đọc to câu trả lời nếu bật).
  onSend: (input: { text: string; mode: ChatMode; fileIds: number[]; voice?: boolean }) => void
}

interface PendingFile {
  key: string
  name: string
  mime: string
  size: number
  // Ảnh: link tạm trong máy để xem trước trước khi gửi.
  previewUrl: string | null
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
    (text: string, voice = false) => {
      const content = text.trim()
      if ((!content && files.length === 0) || busy || uploading || content.length > MAX_MESSAGE_CHARS) return
      onSend({ text: content, mode, fileIds: files.flatMap((f) => (f.uploaded ? [f.uploaded.id] : [])), voice })
      setMode('chat')
      setFiles([])
    },
    [busy, files, mode, onSend, uploading],
  )

  const handleSpeechError = useCallback((message: string) => toast.error(message), [])
  // Nói xong tự gửi (đang chạy xe không phải bấm Gửi).
  const handleSpeechFinal = useCallback((text: string) => submit(text, true), [submit])
  const speech = useSpeechRecognition({ onFinal: handleSpeechFinal, onError: handleSpeechError })
  const startListening = () => {
    // Đang đọc trả lời thì dừng đọc trước khi nghe.
    void Voice.stopSpeaking().catch(() => null)
    speech.start()
  }
  // Chưa gõ gì thì ô gửi thành nút micro lớn (31 mục 3.5): dễ bấm khi đang chạy xe.
  const showMic = speech.supported && (speech.listening || (!draft.trim() && files.length === 0))

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
      const mime = file.type || ''
      const previewUrl = isImageFile(mime, file.name) ? URL.createObjectURL(file) : null
      setFiles((prev) => [...prev, { key, name: file.name, mime, size: file.size, previewUrl, uploaded: null }])
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
        {files.length > 0 && (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {files.map((file) => (
              <div key={file.key} className="relative shrink-0">
                {file.previewUrl ? (
                  <img src={file.previewUrl} alt={file.name} className="size-16 rounded-xl object-cover" />
                ) : (
                  <div className="flex h-16 w-40 items-center gap-2 rounded-xl border bg-card px-2.5">
                    <FileText className="size-5 shrink-0 text-primary" />
                    <span className="min-w-0">
                      <span className="block text-xs font-medium" title={file.name}>
                        {truncateMiddle(file.name, 20)}
                      </span>
                      <span className="block text-[11px] text-muted-foreground">{[fileKindLabel(file.mime, file.name), formatFileSize(file.size)].filter(Boolean).join(' · ')}</span>
                    </span>
                  </div>
                )}
                {!file.uploaded && (
                  <span className="absolute inset-0 flex items-center justify-center rounded-xl bg-background/60" aria-label="Đang tải lên">
                    <Loader2 className="size-4 animate-spin" />
                  </span>
                )}
                <button
                  type="button"
                  aria-label={`Bỏ tệp ${file.name}`}
                  onClick={() => {
                    if (file.previewUrl) URL.revokeObjectURL(file.previewUrl)
                    setFiles((prev) => prev.filter((f) => f.key !== file.key))
                  }}
                  className="absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full bg-foreground text-background"
                >
                  <X className="size-3" />
                </button>
              </div>
            ))}
          </div>
        )}
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
          {showMic ? (
            <button
              type="button"
              aria-label={speech.listening ? 'Dừng nghe' : 'Nói với trợ lý'}
              disabled={busy && !speech.listening}
              onClick={() => (speech.listening ? speech.stop() : startListening())}
              className={cn(
                'relative flex size-14 shrink-0 items-center justify-center rounded-full text-white shadow-md transition-transform active:scale-95 disabled:opacity-50',
                speech.listening ? 'bg-destructive' : 'bg-primary',
              )}
            >
              {speech.listening && <span className="absolute inset-0 animate-ping rounded-full bg-destructive/40" aria-hidden />}
              {busy && !speech.listening ? <Loader2 className="size-6 animate-spin" /> : speech.listening ? <Square className="relative size-5 fill-current" /> : <Mic className="size-7" />}
            </button>
          ) : (
            <Button
              type="submit"
              size="icon"
              className="size-11 shrink-0 rounded-full"
              aria-label="Gửi"
              disabled={busy || uploading || tooLong || (!draft.trim() && files.length === 0)}
            >
              {busy ? <Loader2 className="size-5 animate-spin" /> : <Send className="size-5" />}
            </Button>
          )}
        </div>
      </div>
    </form>
  )
}
