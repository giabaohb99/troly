import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { SettingSection, SubPage } from '@/modules/setting/components/sub-page'
import { getAiCost } from '@/shared/api/ai-cost-api'
import { CostBars } from '@/shared/components/cost-bars'
import { ErrorState } from '@/shared/components/error-state'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { queryKeys } from '@/shared/constants/query-keys'
import { formatModelLabel, formatUsd, toDateKey } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

const PURPOSE_LABEL: Record<string, string> = {
  chat: 'Trò chuyện',
  summary: 'Tóm tắt',
  research: 'Tìm sâu',
  bank_extract: 'Đọc thông báo ngân hàng',
  trip_extract: 'Đọc lịch trình',
  trip_evaluate: 'Đánh giá chuyến',
  file_extract: 'Đọc tệp',
  memory: 'Ghi nhớ',
}

function Breakdown({ rows }: { rows: { label: string; usd: number }[] }) {
  const total = rows.reduce((sum, r) => sum + r.usd, 0) || 1
  return (
    <ul className="flex flex-col gap-2 text-sm">
      {[...rows].sort((a, b) => b.usd - a.usd).map((row) => (
        <li key={row.label} className="flex flex-col gap-1">
          <span className="flex justify-between">
            <span>{row.label}</span>
            <span className="tabular-nums">{formatUsd(row.usd)}</span>
          </span>
          <span className="h-1.5 overflow-hidden rounded-full bg-secondary">
            <span className="block h-full rounded-full bg-primary" style={{ width: `${(row.usd / total) * 100}%` }} />
          </span>
        </li>
      ))}
    </ul>
  )
}

// Chi phí AI (31 mục 3.5 Cài đặt, settings_ai_cost): tháng so với mức cảnh báo 200 USD, cột theo ngày, theo việc,
// theo model, tỉ lệ đọc cache. Không có trần ngày (QĐ-15).
export function AiCostPage() {
  const [month] = useState(() => toDateKey(new Date()).slice(0, 7))
  const cost = useQuery({ queryKey: queryKeys.report.aiCost(month), queryFn: () => getAiCost(month) })
  const d = cost.data
  return (
    <SubPage title="Chi phí AI" subtitle={`Tháng ${Number(month.slice(5))}/${month.slice(0, 4)}`}>
      {cost.isPending && <SkeletonList />}
      {cost.isError && <ErrorState error={cost.error} onRetry={() => void cost.refetch()} />}
      {d && (
        <>
          <SettingSection title="Tháng này">
            <div className="flex flex-col gap-2">
              <p className="flex items-baseline justify-between">
                <span className="text-2xl font-bold tabular-nums">{formatUsd(d.total_usd)}</span>
                <span className="text-xs text-muted-foreground">mức cảnh báo {formatUsd(d.monthly_warn_usd)}</span>
              </p>
              <div className="h-2 overflow-hidden rounded-full bg-secondary">
                <div className={cn('h-full rounded-full', d.total_usd > d.monthly_warn_usd ? 'bg-destructive' : 'bg-primary')} style={{ width: `${Math.min(100, (d.total_usd / d.monthly_warn_usd) * 100)}%` }} />
              </div>
              <CostBars days={d.by_day} />
              <p className="text-xs text-muted-foreground">
                Hôm nay {formatUsd(d.today_usd)}
                {d.cache_read_ratio !== null && ` · đọc cache ${Math.round(d.cache_read_ratio * 100)}%`}. Vượt mức chỉ báo, không chặn.
              </p>
            </div>
          </SettingSection>
          <SettingSection title="Theo việc">
            <Breakdown rows={d.by_purpose.map((r) => ({ label: PURPOSE_LABEL[r.purpose] ?? r.purpose, usd: r.usd }))} />
          </SettingSection>
          <SettingSection title="Theo model">
            <Breakdown rows={d.by_model.map((r) => ({ label: formatModelLabel(r.model) ?? r.model, usd: r.usd }))} />
          </SettingSection>
        </>
      )}
    </SubPage>
  )
}
