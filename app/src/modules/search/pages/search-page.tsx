import { useEffect, useMemo, useState } from 'react'
import { Bot, ChevronLeft, FileText, Loader2, MessageCircle, SearchX, StickyNote, X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { apiGet } from '@/core/api/http-client'
import { openExternal } from '@/core/native/open-external'
import { searchEverything, type SearchHit, type SearchSource } from '@/modules/search/api/search-api'
import { NoteDialog } from '@/modules/search/components/note-dialog'
import { splitSnippet } from '@/modules/search/utils/snippet'
import { queryKeys } from '@/shared/constants/query-keys'
import { EmptyState } from '@/shared/components/empty-state'
import { ErrorState } from '@/shared/components/error-state'
import { Button } from '@/shared/ui/button'
import { formatDayTitle, toDateKey } from '@/shared/utils/format'
import { screenToRoute } from '@/shared/utils/screen-route'
import { cn } from '@/shared/utils/cn'

// Phase 1 có ghi chú, chat, tệp; hộp tin từ Phase 2, lịch trình từ Phase 4 (20 mục 3.8).
const FILTERS: { value: SearchSource | null; label: string }[] = [
  { value: null, label: 'Tất cả' },
  { value: 'note', label: 'Ghi chú' },
  { value: 'chat', label: 'Chat' },
  { value: 'file', label: 'Tệp' },
]

const GROUPS: { source: SearchSource; label: string; icon: typeof StickyNote }[] = [
  { source: 'note', label: 'GHI CHÚ', icon: StickyNote },
  { source: 'file', label: 'TỆP', icon: FileText },
  { source: 'chat', label: 'CHAT', icon: MessageCircle },
]

function Snippet({ text }: { text: string }) {
  return (
    <>
      {splitSnippet(text).map((part, index) =>
        part.bold ? (
          <strong key={index} className="text-foreground">
            {part.text}
          </strong>
        ) : (
          <span key={index}>{part.text}</span>
        ),
      )}
    </>
  )
}

// Màn Tìm (31 mục 3.5): một ô tìm chung, gõ xong 300 ms thì tìm, kết quả nhóm theo loại.
export function SearchPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [text, setText] = useState(params.get('q') ?? '')
  const [debounced, setDebounced] = useState(text.trim())
  const [filter, setFilter] = useState<SearchSource | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(text.trim())
      setParams(text.trim() ? { q: text.trim() } : {}, { replace: true })
    }, 300)
    return () => clearTimeout(timer)
  }, [text, setParams])

  const results = useQuery({
    queryKey: queryKeys.search.results(debounced, filter ?? ''),
    queryFn: ({ signal }) => searchEverything(debounced, filter ? [filter] : null, signal),
    enabled: debounced.length >= 2,
    staleTime: 30_000,
  })

  const grouped = useMemo(() => GROUPS.map((g) => ({ ...g, items: (results.data?.items ?? []).filter((hit) => hit.source === g.source) })).filter((g) => g.items.length > 0), [results.data])

  async function openFile(fileId: number) {
    try {
      const file = await apiGet<{ download_url: string }>(`/files/${fileId}`)
      await openExternal(file.download_url)
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  // Đi từ hành động của trợ lý: /tim?ghi-chu=ID mở ghi chú, /tim?tep=ID mở tệp (note_detail, file_detail).
  const [noteId, setNoteId] = useState<number | null>(() => Number(params.get('ghi-chu')) || null)
  const fileParam = Number(params.get('tep')) || null
  useEffect(() => {
    if (fileParam) void openFile(fileParam)
  }, [fileParam])

  function openHit(hit: SearchHit) {
    if (hit.source === 'note') return setNoteId(hit.id)
    if (hit.source === 'file') return void openFile(hit.id)
    if (hit.open) navigate(screenToRoute(hit.open.screen, hit.open.params))
    else navigate(hit.source === 'chat' ? '/' : `/?hoi=${encodeURIComponent(hit.title)}`)
  }

  return (
    <div className="flex flex-col gap-4 pb-8">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" aria-label="Quay lại" onClick={() => navigate(-1)}>
          <ChevronLeft className="size-5" />
        </Button>
        <div className="relative flex-1">
          <input
            autoFocus
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Tìm, gõ không dấu cũng được"
            aria-label="Tìm"
            className="h-11 w-full rounded-full bg-secondary px-4 pr-10 text-base outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring"
          />
          {text && (
            <button type="button" aria-label="Xóa chữ" onClick={() => setText('')} className="absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground">
              <X className="size-4" />
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => setFilter(f.value)}
            className={cn('rounded-full border px-3 py-1 text-sm', filter === f.value && 'border-primary bg-primary/15 text-primary')}
          >
            {f.label}
          </button>
        ))}
      </div>

      {debounced.length < 2 && <p className="text-center text-sm text-muted-foreground">Gõ ít nhất 2 ký tự để tìm.</p>}
      {results.isFetching && !results.data && (
        <div className="flex justify-center py-8 text-muted-foreground">
          <Loader2 className="size-6 animate-spin" />
        </div>
      )}
      {results.isError && <ErrorState error={results.error} onRetry={() => void results.refetch()} />}
      {results.isSuccess && grouped.length === 0 && <EmptyState icon={SearchX} text="Không thấy kết quả. Thử từ khác hoặc hỏi trợ lý." />}

      {grouped.map((group) => (
        <section key={group.source} className="flex flex-col gap-1">
          <h2 className="text-xs font-semibold tracking-wide text-muted-foreground">{group.label}</h2>
          {group.items.map((hit) => (
            <button key={`${hit.source}-${hit.id}`} type="button" onClick={() => openHit(hit)} className="flex gap-3 rounded-xl px-1 py-2 text-left hover:bg-secondary">
              <group.icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1">
                <span className="flex justify-between gap-2">
                  <span className="truncate font-medium">{hit.title}</span>
                  {hit.date && <span className="shrink-0 text-xs text-muted-foreground">{formatDayTitle(toDateKey(hit.date)).split(', ')[1]}</span>}
                </span>
                <span className="line-clamp-2 text-sm text-muted-foreground">
                  <Snippet text={hit.snippet} />
                </span>
              </span>
            </button>
          ))}
        </section>
      ))}

      {debounced.length >= 2 && (
        <Button variant="secondary" onClick={() => navigate(`/?hoi=${encodeURIComponent(`Tìm giúp: ${debounced}`)}`)}>
          <Bot className="size-4" />
          Hỏi trợ lý về "{debounced}"
        </Button>
      )}
      {noteId && <NoteDialog noteId={noteId} onClose={() => setNoteId(null)} />}
    </div>
  )
}
