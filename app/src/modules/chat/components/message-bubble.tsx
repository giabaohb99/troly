import type { ReactNode } from 'react'
import { MessageText } from '@/modules/chat/components/message-text'
import { AttachmentPreview } from '@/modules/chat/components/attachment-preview'
import { CitationList } from '@/modules/chat/components/citation-list'
import { FileCard } from '@/modules/chat/components/file-card'
import type { Attachment, Citation } from '@/modules/chat/types/chat'
import { formatModelLabel } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

interface MessageBubbleProps {
  // id tin, để đường dẫn sâu từ thông báo cuộn tới đúng tin.
  messageId?: number
  role: 'user' | 'assistant' | 'system'
  text: string
  model?: string | null
  citations?: Citation[] | null
  attachments?: Attachment[] | null
  children?: ReactNode
}

export function MessageBubble({ messageId, role, text, model, citations, attachments, children }: MessageBubbleProps) {
  if (role === 'system') {
    return <p className="self-center rounded-full bg-secondary px-3 py-1 text-xs text-muted-foreground">{text}</p>
  }
  const modelLabel = role === 'assistant' ? formatModelLabel(model) : null
  const usedWeb = (citations?.length ?? 0) > 0
  return (
    <div id={messageId ? `tin-${messageId}` : undefined} className={cn('flex scroll-mt-4 flex-col gap-1.5', role === 'user' ? 'items-end' : 'items-start')}>
      {role === 'user' && attachments && attachments.length > 0 && (
        <div className="flex max-w-[85%] flex-wrap justify-end gap-1.5">
          {attachments.map((file) => (
            <AttachmentPreview key={file.file_id} attachment={file} />
          ))}
        </div>
      )}
      {text && (
        <p
          className={cn(
            'max-w-[85%] rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap break-words',
            role === 'user' ? 'rounded-br-md bg-primary text-primary-foreground' : 'rounded-bl-md border bg-card',
          )}
        >
          <MessageText text={text} />
        </p>
      )}
      {role === 'assistant' &&
        attachments?.map((file) => <FileCard key={file.file_id} file={{ file_id: file.file_id, name: file.name ?? 'Tệp', mime: file.mime ?? '', size_bytes: file.size_bytes }} />)}
      {modelLabel && (
        <span className="px-1 text-[11px] text-muted-foreground/80">
          {modelLabel}
          {usedWeb && ' · có tìm web'}
        </span>
      )}
      {citations && <CitationList citations={citations} />}
      {children}
    </div>
  )
}
