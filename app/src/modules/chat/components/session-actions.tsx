import { useState } from 'react'
import { Loader2, Pencil, Pin, PinOff, Trash2 } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { deleteConversation, updateSession } from '@/modules/chat/api/chat-api'
import type { ChatSession } from '@/modules/chat/types/chat'
import { sessionTitle } from '@/modules/chat/utils/sessions'
import { queryKeys } from '@/shared/constants/query-keys'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'

// Đổi tên, ghim, xóa một phiên (QĐ-51): dùng chung cho ngăn kéo Các phiên và tiêu đề màn chat.
export function useSessionMutations(onDeleted?: (id: number) => void) {
  const queryClient = useQueryClient()
  const refresh = (id: number) => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.chat.sessionsAll })
    void queryClient.invalidateQueries({ queryKey: queryKeys.chat.session(id) })
    void queryClient.invalidateQueries({ queryKey: queryKeys.chat.today })
  }
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: { title?: string; pinned?: boolean } }) => updateSession(id, patch),
    onSuccess: (_data, { id }) => refresh(id),
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  const remove = useMutation({
    mutationFn: (id: number) => deleteConversation(id),
    onSuccess: (_data, id) => {
      toast.success('Đã xóa phiên')
      queryClient.removeQueries({ queryKey: queryKeys.chat.session(id) })
      refresh(id)
      onDeleted?.(id)
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  return { update, remove }
}

export function RenameSessionDialog({ session, open, onOpenChange, onSave, saving }: { session: ChatSession | null; open: boolean; onOpenChange: (open: boolean) => void; onSave: (title: string) => void; saving: boolean }) {
  const [title, setTitle] = useState('')
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next) setTitle(session?.title ?? '')
        onOpenChange(next)
      }}
    >
      <DialogContent
        onOpenAutoFocus={() => setTitle(session?.title ?? '')}
      >
        <DialogHeader>
          <DialogTitle>Đổi tên phiên</DialogTitle>
          <DialogDescription className="sr-only">Tên giúp tìm lại phiên này</DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            if (title.trim()) onSave(title.trim())
          }}
        >
          <Input autoFocus value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} placeholder={sessionTitle(session)} aria-label="Tên phiên" />
          <Button type="submit" disabled={saving || !title.trim()}>
            {saving && <Loader2 className="size-4 animate-spin" />}
            Lưu
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// Menu một phiên: Đổi tên, Ghim hoặc Bỏ ghim, Xóa (hỏi lại).
export function SessionActionsDialog({ session, onClose, onDeleted }: { session: ChatSession | null; onClose: () => void; onDeleted?: (id: number) => void }) {
  const { update, remove } = useSessionMutations(onDeleted)
  const [renaming, setRenaming] = useState<ChatSession | null>(null)
  const [deleting, setDeleting] = useState<ChatSession | null>(null)
  return (
    <>
      <Dialog open={!!session} onOpenChange={(open) => !open && onClose()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="truncate">{sessionTitle(session)}</DialogTitle>
            <DialogDescription className="sr-only">Việc với phiên này</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-1">
            <Button
              variant="ghost"
              className="justify-start"
              onClick={() => {
                setRenaming(session)
                onClose()
              }}
            >
              <Pencil className="size-4" />
              Đổi tên
            </Button>
            <Button
              variant="ghost"
              className="justify-start"
              onClick={() => {
                if (session) update.mutate({ id: session.id, patch: { pinned: !session.pinned } }, { onSuccess: () => toast.success(session.pinned ? 'Đã bỏ ghim' : 'Đã ghim phiên') })
                onClose()
              }}
            >
              {session?.pinned ? <PinOff className="size-4" /> : <Pin className="size-4" />}
              {session?.pinned ? 'Bỏ ghim' : 'Ghim'}
            </Button>
            <Button
              variant="ghost"
              className="justify-start text-destructive"
              onClick={() => {
                setDeleting(session)
                onClose()
              }}
            >
              <Trash2 className="size-4" />
              Xóa phiên
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <RenameSessionDialog
        session={renaming}
        open={!!renaming}
        onOpenChange={(open) => !open && setRenaming(null)}
        saving={update.isPending}
        onSave={(title) => renaming && update.mutate({ id: renaming.id, patch: { title } }, { onSuccess: () => setRenaming(null) })}
      />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Xóa phiên ${sessionTitle(deleting)}?`}
        description="Toàn bộ tin nhắn trong phiên này sẽ bị xóa. Chi tiêu, lịch, ghi chú đã ghi vẫn giữ nguyên."
        onConfirm={() => deleting && remove.mutate(deleting.id)}
      />
    </>
  )
}
