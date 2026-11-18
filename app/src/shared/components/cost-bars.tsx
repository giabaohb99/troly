import { formatUsd } from '@/shared/utils/format'

// Cột chi phí AI theo ngày (31 mục 3.5): không có trần ngày (QĐ-15), chỉ để nhìn xu hướng.
export function CostBars({ days }: { days: { date: string; usd: number }[] }) {
  const max = Math.max(0.01, ...days.map((d) => d.usd))
  if (days.length === 0) return null
  return (
    <div className="flex h-20 items-end gap-[2px]" role="img" aria-label="Chi phí AI theo ngày">
      {days.map((day) => (
        <span key={day.date} title={`${day.date.slice(8)}/${day.date.slice(5, 7)}: ${formatUsd(day.usd)}`} className="flex-1 rounded-t-sm bg-primary/70" style={{ height: `${Math.max(2, (day.usd / max) * 100)}%` }} />
      ))}
    </div>
  )
}
