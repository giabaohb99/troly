import type { LucideIcon } from 'lucide-react'
import { EmptyState } from '@/shared/components/empty-state'
import { PageHeader } from '@/shared/components/page-header'

// Màn chưa tới phase vẫn có ô trên thanh dưới, hiện trạng thái rỗng (31 mục 2).
export function ComingSoon({ title, icon, phase, text }: { title: string; icon: LucideIcon; phase: number; text: string }) {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={title} />
      <EmptyState icon={icon} text={`${text} Có từ Phase ${phase}.`} />
    </div>
  )
}
