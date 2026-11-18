import { FileText } from 'lucide-react'
import type { ReactNode } from 'react'
import { MessageText } from '@/modules/chat/components/message-text'
import { CitationList } from '@/modules/chat/components/citation-list'
import type { Attachment, Citation } from '@/modules/chat/types/chat'
import { formatModelLabel } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

interface MessageBubbleProps {
  role: 'user' | 'assistant' | 'system'
  text: string
  model?: string | null
  citations?: Citation[] | null
  attachments?: Attachment[] | null
  children?: ReactNode
}

export function MessageBubble({ role, text, model, citations, attachments, children }: MessageBubbleProps) {
  if (role === 'system') {
    return <p className="self-center rounded-full bg-secondary px-3 py-1 text-xs text-muted-foreground">{text}</p>
  }
  const modelLabel = role === 'assistant' ? formatModelLabel(model) : null
  const usedWeb = (citations?.length ?? 0) > 0
  return (
    <div className={cn('flex flex-col gap-1.5', role === 'user' ? 'items-end' : 'items-start')}>
      {attachments && attachments.length > 0 && (
        <div className="flex flex-wrap justify-end gap-1">
          {attachments.map((file) => (
            <span key={file.file_id} className="inline-flex items-center gap-1 rounded-lg bg-secondary px-2 py-1 text-xs">
              <FileText className="size-3.5" />
              {file.name}
            </span>
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
