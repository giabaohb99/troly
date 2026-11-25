import { useEffect, useMemo, useRef, useState } from 'react'
import { Loader2, MessageSquarePlus, MoreVertical, Pin, Search, X } from 'lucide-react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { Dialog as DialogPrimitive } from 'radix-ui'
import { listSessions } from '@/modules/chat/api/chat-api'
import { SessionActionsDialog } from '@/modules/chat/components/session-actions'
import type { ChatSession } from '@/modules/chat/types/chat'
import { matchSession, sessionPreview, sessionTitle, sortSessions } from '@/modules/chat/utils/sessions'
import { queryKeys } from '@/shared/constants/query-keys'
import { ErrorState } from '@/shared/components/error-state'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { formatWhen } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

interface SessionsDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentId: number | null
  onSelect: (id: number) => void
  onNew: () => void
  creating: boolean
  onDeleted: (id: number) => void
}

// Một dòng phiên: giữ lâu (hoặc bấm nút ba chấm) mở menu Đổi tên, Ghim, Xóa.
function SessionRow({ session, active, onOpen, onMenu }: { session: ChatSession; active: boolean; onOpen: () => void; onMenu: () => void }) {
  const timer = useRef<number | null>(null)
  const longPressed = useRef(false)
  const cancel = () => {
    if (timer.current) window.clearTimeout(timer.current)
    timer.current = null
  }
  return (
    <li className={cn('flex items-center gap-1 rounded-xl', active && 'bg-primary/10')}>
      <button
        type="button"
        className="min-w-0 flex-1 px-3 py-2.5 text-left"
        onPointerDown={() => {
          longPressed.current = false
          cancel()
          timer.current = window.setTimeout(() => {
            longPressed.current = true
            onMenu()
          }, 550)
        }}
        onPointerUp={cancel}
        onPointerLeave={cancel}
        onPointerMove={(e) => e.movementY !== 0 && cancel()}
        onContextMenu={(e) => e.preventDefault()}
        onClick={() => {
          if (!longPressed.current) onOpen()
        }}
      >
        <span className="flex items-center gap-1.5">
          {session.pinned && <Pin className="size-3.5 shrink-0 text-primary" aria-label="Đã ghim" />}
          <span className={cn('min-w-0 flex-1 truncate text-sm', active ? 'font-semibold text-primary' : 'font-medium')}>{sessionTitle(session)}</span>
          {session.last_message_at && <span className="shrink-0 text-[11px] text-muted-foreground">{formatWhen(session.last_message_at)}</span>}
        </span>
        {sessionPreview(session) && <span className="mt-0.5 block truncate text-xs text-muted-foreground">{sessionPreview(session)}</span>}
      </button>
      <Button size="icon" variant="ghost" className="size-9 shrink-0" aria-label={`Menu phiên ${sessionTitle(session)}`} onClick={onMenu}>
        <MoreVertical className="size-4" />
      </Button>
    </li>
  )
}

// Ngăn kéo Các phiên (QĐ-51 bước 1): ô tìm, Phiên mới, phiên ghim ở trên, còn lại theo lần nhắn cuối.
export function SessionsDrawer({ open, onOpenChange, currentId, onSelect, onNew, creating, onDeleted }: SessionsDrawerProps) {
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  const [menu, setMenu] = useState<ChatSession | null>(null)
  // Tìm trên máy chủ sau khi ngừng gõ 300 ms; trong lúc chờ lọc tại chỗ.
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(q.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [q])
  const list = useInfiniteQuery({
    queryKey: queryKeys.chat.sessions(query),
    queryFn: ({ pageParam }) => listSessions(query, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    enabled: open,
  })
  const items = useMemo(() => sortSessions((list.data?.pages ?? []).flatMap((p) => p.items)).filter((s) => matchSession(s, q)), [list.data, q])

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content
          className="fixed inset-y-0 left-0 z-50 flex w-[85%] max-w-sm flex-col gap-3 border-r bg-background px-3 pt-[max(env(safe-area-inset-top),1rem)] pb-[max(env(safe-area-inset-bottom),1rem)] shadow-xl data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left data-[state=open]:animate-in data-[state=open]:slide-in-from-left"
          aria-describedby={undefined}
        >
          <div className="flex items-center gap-2 px-1">
            <DialogPrimitive.Title className="min-w-0 flex-1 text-lg font-bold">Các phiên</DialogPrimitive.Title>
            <DialogPrimitive.Close asChild>
              <Button size="icon" variant="ghost" aria-label="Đóng">
                <X className="size-5" />
              </Button>
            </DialogPrimitive.Close>
          </div>
          <Button disabled={creating} onClick={onNew}>
            {creating ? <Loader2 className="size-4 animate-spin" /> : <MessageSquarePlus className="size-4" />}
            Phiên mới
          </Button>
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm phiên" className="pl-9" aria-label="Tìm phiên" />
          </div>
          <div className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1">
            {list.isPending && (
              <div className="flex justify-center py-6 text-muted-foreground">
                <Loader2 className="size-5 animate-spin" />
              </div>
            )}
            {list.isError && <ErrorState error={list.error} onRetry={() => void list.refetch()} />}
            {list.isSuccess && items.length === 0 && <p className="px-2 py-6 text-center text-sm text-muted-foreground">{q.trim() ? 'Không có phiên nào khớp.' : 'Chưa có phiên nào.'}</p>}
            <ul className="flex flex-col gap-0.5">
              {items.map((s) => (
                <SessionRow key={s.id} session={s} active={s.id === currentId} onOpen={() => onSelect(s.id)} onMenu={() => setMenu(s)} />
              ))}
            </ul>
            {list.hasNextPage && (
              <Button variant="ghost" className="mt-1 w-full" disabled={list.isFetchingNextPage} onClick={() => void list.fetchNextPage()}>
                {list.isFetchingNextPage && <Loader2 className="size-4 animate-spin" />}
                Xem thêm
              </Button>
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
      <SessionActionsDialog session={menu} onClose={() => setMenu(null)} onDeleted={onDeleted} />
    </DialogPrimitive.Root>
  )
}
