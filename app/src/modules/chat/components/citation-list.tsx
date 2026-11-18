import { openExternal } from '@/core/native/open-external'
import type { Citation } from '@/modules/chat/types/chat'

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

// Nguồn của câu trả lời có tìm web, bấm mở trang bằng trình duyệt ngoài (31 mục 3.5).
export function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
      <span>Nguồn:</span>
      {citations.map((citation, index) => (
        <button
          key={`${citation.url}-${index}`}
          type="button"
          title={citation.title}
          onClick={() => void openExternal(citation.url)}
          className="max-w-[12rem] truncate rounded-full border px-2 py-0.5 text-foreground/80 hover:border-primary hover:text-primary"
        >
          [{index + 1}] {hostOf(citation.url)}
        </button>
      ))}
    </div>
  )
}
