import { APP_COLORS, APP_LABELS, type InboxApp } from '@/modules/inbox/types/inbox'
import { cn } from '@/shared/utils/cn'

// Nhãn app bằng chữ ngắn trên nền token, không dùng logo thương hiệu (31 mục 3.1).
export function AppTag({ app }: { app: InboxApp }) {
  return <span className={cn('inline-flex shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-semibold', APP_COLORS[app])}>{APP_LABELS[app]}</span>
}
