import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

// Thẻ rỗng: nói vì sao trống và làm gì tiếp (31 mục 3.4).
export function EmptyState({ icon: Icon, text, children }: { icon: LucideIcon; text: string; children?: ReactNode }) {
  return (
    <section className="flex flex-col items-center gap-3 rounded-2xl border bg-card px-5 py-8 text-center">
      <Icon className="size-10 text-primary" />
      <p className="text-sm text-muted-foreground">{text}</p>
      {children}
    </section>
  )
}
