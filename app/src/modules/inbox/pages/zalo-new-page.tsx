import { useMemo, useState } from 'react'
import { ChevronLeft, Search, UserRound, Users } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { listZaloContacts } from '@/modules/inbox/api/zalo-api'
import { needsZaloLogin, zaloSendErrorText } from '@/modules/inbox/utils/zalo'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'

const fold = (t: string) => t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase()

// Tin Zalo mới (QĐ-52): chọn người hoặc nhóm trong danh bạ Zalo rồi mở khung chat.
export function ZaloNewPage() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const contacts = useQuery({ queryKey: ['zalo', 'contacts'], queryFn: listZaloContacts, staleTime: 5 * 60_000, retry: 0 })
  const items = useMemo(() => (contacts.data?.items ?? []).filter((c) => !q.trim() || fold(c.name).includes(fold(q.trim()))), [contacts.data, q])

  return (
    <div className="flex flex-col gap-3 pb-8">
      <div className="flex items-center gap-1">
        <Button size="icon" variant="ghost" aria-label="Quay lại" onClick={() => navigate('/hop-tin?loai=zalo')}>
          <ChevronLeft className="size-5" />
        </Button>
        <h1 className="text-lg font-bold">Tin Zalo mới</h1>
      </div>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm người, nhóm" className="pl-9" aria-label="Tìm người, nhóm" />
      </div>
      {contacts.isPending && <SkeletonList />}
      {contacts.isError && (
        <div className="flex flex-col items-start gap-2 text-sm text-muted-foreground">
          {zaloSendErrorText(contacts.error)}
          {needsZaloLogin(contacts.error) && (
            <Button size="sm" onClick={() => navigate('/cai-dat/zalo')}>
              Quét mã đăng nhập
            </Button>
          )}
        </div>
      )}
      <ul className="divide-y">
        {items.map((c) => (
          <li key={c.conversation_key}>
            <button type="button" className="flex w-full items-center gap-3 py-2.5 text-left" onClick={() => navigate(`/zalo/${encodeURIComponent(c.conversation_key)}`)}>
              {c.avatar ? (
                <img src={c.avatar} alt="" className="size-10 shrink-0 rounded-full object-cover" loading="lazy" referrerPolicy="no-referrer" />
              ) : (
                <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-app-2/20 text-app-2">
                  {c.thread_type === 'group' ? <Users className="size-5" /> : <UserRound className="size-5" />}
                </span>
              )}
              <span className="min-w-0 flex-1 truncate font-medium">{c.name}</span>
              {c.thread_type === 'group' && <span className="text-xs text-muted-foreground">Nhóm</span>}
            </button>
          </li>
        ))}
        {contacts.isSuccess && items.length === 0 && <li className="py-6 text-center text-sm text-muted-foreground">Không thấy ai khớp.</li>}
      </ul>
    </div>
  )
}
