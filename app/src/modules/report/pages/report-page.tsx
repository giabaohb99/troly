import { useState, type ReactNode } from 'react'
import { Bot, CalendarDays, ChevronRight, Inbox, Smartphone, TriangleAlert, Wallet } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getDashboard, type Card } from '@/modules/report/api/report-api'
import { GymCard } from '@/modules/report/components/gym-card'
import { useFeatures } from '@/shared/hooks/use-features'
import { getAiCost } from '@/shared/api/ai-cost-api'
import { CostBars } from '@/shared/components/cost-bars'
import { ErrorState } from '@/shared/components/error-state'
import { PageHeader } from '@/shared/components/page-header'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { queryKeys } from '@/shared/constants/query-keys'
import { formatDayTitle, formatMoney, formatMoneyShort, formatTime, formatUsd, toDateKey } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

function ReportCard<T>({ icon: Icon, title, card, to, children }: { icon: typeof Wallet; title: string; card: Card<T>; to?: string; children: (data: T) => ReactNode }) {
  const navigate = useNavigate()
  return (
    <section className="rounded-2xl border bg-card p-4">
      <button type="button" disabled={!to} onClick={() => to && navigate(to)} className="mb-2 flex w-full items-center gap-2 text-left font-semibold">
        <Icon className="size-4 text-primary" />
        <span className="flex-1">{title}</span>
        {to && <ChevronRight className="size-4 text-muted-foreground" />}
      </button>
      {card.status === 'ok' && card.data ? (
        children(card.data)
      ) : card.status === 'disabled' ? (
        <p className="text-sm text-muted-foreground">{card.message ?? 'Chưa bật.'}</p>
      ) : (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <TriangleAlert className="size-4 text-warning" />
          {card.message ?? 'Thẻ này đang lỗi, các thẻ khác vẫn đúng.'}
        </p>
      )}
    </section>
  )
}

function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: 'warn' | 'bad' }) {
  return (
    <div className="flex flex-col">
      <span className={cn('text-xl font-bold tabular-nums', tone === 'warn' && 'text-warning', tone === 'bad' && 'text-destructive')}>{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  )
}

function changeText(current: number, previous: number | null): string | null {
  if (!previous) return null
  const pct = Math.round(((current - previous) / previous) * 100)
  if (pct === 0) return 'bằng tháng trước'
  return `${pct > 0 ? 'hơn' : 'kém'} tháng trước ${Math.abs(pct)}%`
}

// Báo cáo (31 mục 3.5): mỗi thẻ lỗi riêng được; không có nút gửi báo cáo (QĐ-11).
export function ReportPage() {
  const [today] = useState(() => toDateKey(new Date()))
  const dashboard = useQuery({ queryKey: queryKeys.report.dashboard(today), queryFn: () => getDashboard(today) })
  const aiCost = useQuery({ queryKey: queryKeys.report.aiCost(today.slice(0, 7)), queryFn: () => getAiCost(today.slice(0, 7)) })
  const cards = dashboard.data?.cards
  const features = useFeatures()

  return (
    <div className="flex flex-col gap-4 pb-8">
      <PageHeader title="Báo cáo" subtitle={formatDayTitle(today)} />
      {dashboard.isPending && <SkeletonList />}
      {dashboard.isError && <ErrorState error={dashboard.error} onRetry={() => void dashboard.refetch()} />}
      {cards && (
        <>
          <ReportCard icon={Wallet} title="Chi tiêu tháng này" card={cards.expense} to="/chi-tieu">
            {(d) => (
              <div className="flex flex-col gap-3">
                <div>
                  <p className="text-2xl font-bold tabular-nums">{formatMoney(d.total_vnd)}</p>
                  <p className="text-xs text-muted-foreground">
                    {[changeText(d.total_vnd, d.previous_total_vnd), d.income_vnd ? `thu ${formatMoneyShort(d.income_vnd)}` : null].filter(Boolean).join(' · ')}
                  </p>
                </div>
                <ul className="flex flex-col gap-1.5 text-sm">
                  {d.top_categories.map((c) => (
                    <li key={c.name} className="flex flex-col gap-1">
                      <span className="flex justify-between">
                        <span>{c.name}</span>
                        <span className="tabular-nums">{formatMoneyShort(c.total_vnd)}</span>
                      </span>
                      <span className="h-1.5 overflow-hidden rounded-full bg-secondary">
                        <span className="block h-full rounded-full bg-primary" style={{ width: `${d.total_vnd ? Math.min(100, (c.total_vnd / d.total_vnd) * 100) : 0}%` }} />
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </ReportCard>

          <ReportCard icon={CalendarDays} title="Lịch tuần này" card={cards.calendar} to="/lich?xem=tuan">
            {(d) => (
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-3 gap-2">
                  <Stat label="sự kiện tuần" value={d.week_events} />
                  {cards.tasks.status === 'ok' && cards.tasks.data && (
                    <>
                      <Stat label="việc hôm nay" value={cards.tasks.data.today} />
                      <Stat label="việc quá hạn" value={cards.tasks.data.overdue} tone={cards.tasks.data.overdue ? 'bad' : undefined} />
                    </>
                  )}
                </div>
                {d.next_event && (
                  <p className="text-sm text-muted-foreground">
                    Kế tiếp: <span className="text-foreground">{d.next_event.title}</span> · {formatDayTitle(toDateKey(d.next_event.start_at)).split(', ')[1]} {formatTime(d.next_event.start_at)}
                  </p>
                )}
              </div>
            )}
          </ReportCard>

          <ReportCard icon={Inbox} title="Hộp tin" card={cards.inbox} to="/hop-tin">
            {(d) => (
              <div className="grid grid-cols-2 gap-2">
                <Stat label="quan trọng chưa xem" value={d.important_unseen} tone={d.important_unseen ? 'warn' : undefined} />
                <Stat label="tin chưa xử lý" value={d.new_count} />
              </div>
            )}
          </ReportCard>

          <ReportCard icon={Bot} title="Chi phí AI" card={cards.ai} to="/cai-dat/chi-phi">
            {(d) => (
              <div className="flex flex-col gap-2">
                <p className="flex items-baseline justify-between">
                  <span className="text-2xl font-bold tabular-nums">{formatUsd(d.month_usd)}</span>
                  <span className="text-xs text-muted-foreground">mức cảnh báo {formatUsd(d.monthly_warn_usd)}</span>
                </p>
                <div className="h-2 overflow-hidden rounded-full bg-secondary">
                  <div className={cn('h-full rounded-full', d.month_usd > d.monthly_warn_usd ? 'bg-destructive' : 'bg-primary')} style={{ width: `${Math.min(100, (d.month_usd / d.monthly_warn_usd) * 100)}%` }} />
                </div>
                {aiCost.data && <CostBars days={aiCost.data.by_day} />}
                <p className="text-xs text-muted-foreground">Hôm nay {formatUsd(d.today_usd)}. Vượt mức chỉ báo, không chặn.</p>
              </div>
            )}
          </ReportCard>

          <ReportCard icon={Smartphone} title="Thiết bị" card={cards.devices} to="/thiet-lap">
            {(d) => (
              <ul className="flex flex-col gap-2 text-sm">
                {d.items.map((device) => (
                  <li key={device.id} className="flex flex-col">
                    <span className="flex justify-between gap-2">
                      <span className="font-medium">{device.name}</span>
                      <span className={device.listener_connected ? 'text-primary' : 'text-warning'}>{device.listener_connected ? 'Đang nghe' : 'Không nghe'}</span>
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {[device.last_event_at ? `tin cuối ${formatTime(device.last_event_at)}` : 'chưa có tin', `chặn ${device.otp_blocked_today} tin OTP hôm nay`].join(' · ')}
                    </span>
                  </li>
                ))}
                {d.items.length === 0 && <li className="text-muted-foreground">Chưa có điện thoại nào.</li>}
              </ul>
            )}
          </ReportCard>
        </>
      )}
      {/* Thẻ Tập luyện (QĐ-54) tải riêng: dashboard lỗi vẫn hiện; chỉ khi máy chủ bật cờ gym. */}
      {features.gym && <GymCard />}
    </div>
  )
}
