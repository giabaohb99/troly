import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { apiGet } from '@/core/api/http-client'
import { ErrorState } from '@/shared/components/error-state'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { formatDayTitle, toDateKey } from '@/shared/utils/format'

interface Note {
  id: number
  title: string
  body: string
  tags: string[] | null
  updated_at: string | null
  created_at: string | null
}

// Xem một ghi chú (màn note_detail, 12 mục 3.9). Phase 1 chỉ xem; sửa ghi chú nhờ trợ lý.
export function NoteDialog({ noteId, onClose }: { noteId: number; onClose: () => void }) {
  const note = useQuery({ queryKey: ['memory', 'note', noteId], queryFn: () => apiGet<Note>(`/memory/notes/${noteId}`) })
  const date = note.data?.updated_at ?? note.data?.created_at

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85dvh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{note.data?.title || 'Ghi chú'}</DialogTitle>
          <DialogDescription>{date ? formatDayTitle(toDateKey(date)) : ' '}</DialogDescription>
        </DialogHeader>
        {note.isPending && <Loader2 className="mx-auto size-6 animate-spin text-muted-foreground" />}
        {note.isError && <ErrorState error={note.error} onRetry={() => void note.refetch()} />}
        {note.data && <p className="text-sm leading-relaxed whitespace-pre-wrap">{note.data.body}</p>}
        {note.data?.tags && note.data.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {note.data.tags.map((tag) => (
              <span key={tag} className="rounded-full bg-secondary px-2 py-0.5 text-xs">
                {tag}
              </span>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
