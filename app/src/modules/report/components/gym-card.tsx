import { useState } from 'react'
import { CircleCheck, Dumbbell, ExternalLink, TriangleAlert } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { getGymReport, GYM_APP_URL, gymDayText, gymLines, type GymPeriod } from '@/modules/report/api/gym-api'
import { openWebLink } from '@/shared/components/rich-text'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/utils/cn'

const PERIODS: { value: GymPeriod; label: string }[] = [
  // Máy chủ tính 7 ngày, 30 ngày tới hôm nay.
  { value: 'week', label: '7 ngày' },
  { value: 'month', label: '30 ngày' },
]

function Line({ label, value, tone }: { label: string; value: string; tone?: 'warn' }) {
  return (
    <p className="flex gap-2 text-sm">
      <span className="w-24 shrink-0 text-muted-foreground">{label}</span>
      <span className={cn('min-w-0', tone === 'warn' && 'text-warning')}>{value}</span>
    </p>
  )
}

// Thẻ Tập luyện trên màn Báo cáo (QĐ-54): buổi đã tập trên buổi theo lịch, bài tăng tạ nổi bật, cân nặng đầu và
// cuối khoảng, đạm trung bình so mục tiêu, buổi hôm nay và ngày mai; nút mở app gym. Lỗi riêng, không kéo thẻ khác.
export function GymCard() {
  const [period, setPeriod] = useState<GymPeriod>('week')
  const report = useQuery({ queryKey: ['report', 'gym', period], queryFn: () => getGymReport(period), retry: 1 })
  const card = report.data
  const data = card?.status === 'ok' ? card.data : null
  const lines = data ? gymLines(data) : null

  return (
    <section className="flex flex-col gap-2 rounded-2xl border bg-card p-4">
      <div className="flex items-center gap-2">
        <Dumbbell className="size-4 text-primary" />
        <h2 className="flex-1 font-semibold">Tập luyện</h2>
        <div className="flex gap-1" role="radiogroup" aria-label="Khoảng thời gian">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              type="button"
              role="radio"
              aria-checked={period === p.value}
              onClick={() => setPeriod(p.value)}
              className={cn('rounded-full border px-2 py-0.5 text-xs', period === p.value ? 'border-primary bg-primary/15 text-primary' : 'text-muted-foreground')}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {report.isPending && <p className="text-sm text-muted-foreground">Đang tải...</p>}
      {(report.isError || card?.status === 'error') && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <TriangleAlert className="size-4 text-warning" />
          {card?.message ?? 'Chưa lấy được số liệu tập luyện.'}
        </p>
      )}
      {card?.status === 'disabled' && <p className="text-sm text-muted-foreground">{card.message ?? 'Chưa nối app gym.'}</p>}

      {data && lines && (
        <>
          <div className="flex items-baseline gap-2">
            <span className={cn('text-2xl font-bold tabular-nums', lines.behind && 'text-warning')}>{lines.sessions}</span>
            <span className="text-xs text-muted-foreground">buổi đã tập / theo lịch</span>
          </div>
          {lines.complete && <p className="-mt-1 text-xs text-muted-foreground">{lines.complete}</p>}
          {lines.lifts.length > 0 && (
            <div className="flex flex-col gap-0.5">
              <span className="text-xs text-muted-foreground">Tăng tạ nổi bật</span>
              {lines.lifts.map((l) => (
                <span key={l} className="text-sm">
                  {l}
                </span>
              ))}
            </div>
          )}
          {lines.weight && <Line label="Cân nặng" value={lines.weight} />}
          {lines.protein && <Line label="Đạm" value={lines.protein} tone={lines.proteinLow ? 'warn' : undefined} />}
          <Line label="Hôm nay" value={gymDayText(data.today)} />
          <Line label="Ngày mai" value={gymDayText(data.tomorrow)} />
          {data.today?.done && (
            <p className="flex items-center gap-1.5 text-xs text-primary">
              <CircleCheck className="size-3.5" />
              Xong buổi hôm nay
            </p>
          )}
        </>
      )}

      <Button variant="outline" size="sm" className="mt-1 self-start" onClick={() => openWebLink(data?.app_url || GYM_APP_URL)}>
        <ExternalLink className="size-4" />
        Mở app gym
      </Button>
    </section>
  )
}
