import {
  BedDouble,
  Check,
  Bike,
  Clock,
  Coffee,
  Copy,
  Mail,
  Landmark,
  MapPin,
  Navigation,
  Phone,
  Ship,
  ShoppingBag,
  TriangleAlert,
  Utensils,
  type LucideIcon,
} from 'lucide-react'
import { toast } from 'sonner'
import { Maps, placeUrl } from '@/core/native/maps'
import type { Risk, Stop, StopBooking, StopCategory, TripFact } from '@/modules/trip/types/trip'
import { bookingLines, canNavigate, formatDuration, formatKm, navigationTarget, stopSearchText } from '@/modules/trip/utils/trip-utils'
import { Button } from '@/shared/ui/button'
import { formatTime } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

const CATEGORY_ICON: Record<StopCategory, LucideIcon> = {
  an_uong: Utensils,
  nghi: Coffee,
  tham_quan: Landmark,
  pha: Ship,
  di_chuyen: Bike,
  khach_san: BedDouble,
  mua_sam: ShoppingBag,
  khac: MapPin,
}

const ROLE_LABEL = { alternative: 'hoặc', backup: 'dự phòng', generic: 'gợi ý chung', via: 'đi qua', main: null } as const

const FACT_LABEL: Partial<Record<TripFact['kind'], string>> = {
  ferry_last: 'Chuyến cuối',
  ferry_first: 'Chuyến đầu',
  checkin: 'Nhận phòng',
  checkout: 'Trả phòng',
  hotline: 'Hotline',
}

function stopTime(stop: Stop): string {
  if (stop.planned_start) return `${stop.approx ? '~' : ''}${formatTime(stop.planned_start)}`
  return stop.time_text ?? ''
}

async function openMap(open: () => Promise<unknown>) {
  try {
    await open()
  } catch {
    toast.error('Không mở được bản đồ.')
  }
}

// Một điểm trong ngày (31 mục 3.5): giờ, loại, tên, km và giờ chạy từ điểm trước, mốc cứng, rủi ro, Dẫn đường, Xem.
// Đặt chỗ từ email (QĐ-49): nơi đặt, mã đặt chỗ (chạm để chép), giờ nhận, trả phòng, số khách, giá, chính sách hủy.
// Đặt chỗ đã hủy thì gạch và ghi *Đã hủy*.
function BookingInfo({ booking }: { booking: StopBooking }) {
  const lines = bookingLines(booking)
  const cancelled = booking.status === 'cancelled'
  const copyRef = () => {
    if (!booking.booking_ref) return
    void navigator.clipboard
      ?.writeText(booking.booking_ref)
      .then(() => toast.success('Đã chép mã đặt chỗ'))
      .catch(() => null)
  }
  return (
    <div className={cn('mt-1 flex flex-col gap-0.5 rounded-xl border bg-primary/5 px-3 py-2 text-xs', cancelled && 'opacity-70')}>
      <span className="flex flex-wrap items-center gap-1.5 font-medium">
        <Mail className="size-3.5 shrink-0 text-primary" />
        <span className={cn(cancelled && 'line-through')}>{lines.head}</span>
        {booking.booking_ref && (
          <button type="button" onClick={copyRef} aria-label="Chép mã đặt chỗ" className="text-primary">
            <Copy className="size-3.5" />
          </button>
        )}
        {cancelled && <span className="rounded-full bg-destructive/15 px-1.5 text-destructive">Đã hủy</span>}
        {booking.status === 'changed' && <span className="rounded-full bg-warning/15 px-1.5 text-warning">Đã đổi</span>}
      </span>
      {lines.times && <span className={cn('text-foreground', cancelled && 'line-through')}>{lines.times}</span>}
      {lines.extra && <span className="text-muted-foreground">{lines.extra}</span>}
      {booking.cancellation && <span className="text-muted-foreground">Hủy: {booking.cancellation}</span>}
    </div>
  )
}

// Dẫn đường: xe hai bánh, tránh cao tốc (30 mục 3.12).
interface StopRowProps {
  stop: Stop
  risks: Risk[]
  facts: TripFact[]
  estimated: boolean
  // Chế độ Chọn điểm: undefined là không chọn; null là điểm này không chọn được (điểm phụ).
  picked?: boolean | null
  onTogglePick?: () => void
}

export function StopRow({ stop, risks, facts, estimated, picked, onTogglePick }: StopRowProps) {
  const Icon = CATEGORY_ICON[stop.category] ?? MapPin
  const role = ROLE_LABEL[stop.role]
  const legParts = [formatKm(stop.leg_km), stop.leg_minutes ? `khoảng ${formatDuration(stop.leg_minutes)}` : null].filter(Boolean)
  const leg = legParts.length ? `${legParts.join(' · ')}${estimated ? ' (ước tính)' : ''}` : ''
  const secondary = stop.role !== 'main' && stop.role !== 'via'
  return (
    <div className={cn('flex gap-3 py-3', secondary && 'pl-6 opacity-80')}>
      {picked !== undefined && (
        <button
          type="button"
          role="checkbox"
          aria-checked={!!picked}
          aria-label={`Chọn ${stop.title}`}
          disabled={picked === null}
          onClick={onTogglePick}
          className={cn('mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md border disabled:opacity-30', picked && 'border-primary bg-primary text-primary-foreground')}
        >
          {picked && <Check className="size-4" />}
        </button>
      )}
      <span className="w-11 shrink-0 pt-0.5 text-sm text-muted-foreground tabular-nums">{stopTime(stop)}</span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex items-start gap-2">
          <Icon className="mt-0.5 size-4 shrink-0 text-primary" />
          <span className="min-w-0 font-medium">
            {role && <span className="mr-1 text-xs font-normal text-muted-foreground">({role})</span>}
            {stop.title}
            {stop.optional && <span className="ml-1 text-xs font-normal text-muted-foreground">tùy chọn</span>}
          </span>
        </span>
        {leg && <span className="text-xs text-muted-foreground">{leg}</span>}
        {facts.map((fact) => (
          <span key={fact.id} className="flex items-center gap-1.5 text-xs">
            <Clock className="size-3.5 text-warning" />
            {FACT_LABEL[fact.kind] ? `${FACT_LABEL[fact.kind]} ${fact.value_time?.slice(0, 5) ?? fact.value_text ?? ''}` : fact.text}
            {stop.fixed && <span className="text-warning">mốc cứng</span>}
          </span>
        ))}
        {facts.length === 0 && stop.fixed && (
          <span className="flex items-center gap-1.5 text-xs text-warning">
            <Clock className="size-3.5" />
            mốc cứng
          </span>
        )}
        {risks.map((risk, index) => (
          <span key={`${risk.code}-${index}`} className={cn('flex items-start gap-1.5 text-xs', risk.level === 'red' ? 'text-destructive' : 'text-warning')}>
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
            <span>
              {risk.message}
              {risk.suggestion && <span className="block text-muted-foreground">{risk.suggestion}</span>}
            </span>
          </span>
        ))}
        {stop.note && <span className="text-xs text-muted-foreground">{stop.note}</span>}
        {stop.cost_note && <span className="text-xs text-muted-foreground">{stop.cost_note}</span>}
        {stop.booking && <BookingInfo booking={stop.booking} />}
        <div className="mt-1 flex flex-wrap gap-2">
          {canNavigate(stop) && (
            <Button
              size="sm"
              onClick={() => void openMap(() => Maps.navigate({ ...navigationTarget(stop), mode: 'l', avoid: 'h' }))}
            >
              <Navigation className="size-4" />
              Dẫn đường
            </Button>
          )}
          {stop.role !== 'generic' && (
            <Button size="sm" variant="outline" onClick={() => void openMap(() => Maps.openUrl({ url: placeUrl(stopSearchText(stop), stop.place_id) }))}>
              Xem
            </Button>
          )}
          {stop.phone && (
            <Button size="sm" variant="ghost" asChild>
              <a href={`tel:${stop.phone.replace(/[^\d+]/g, '')}`}>
                <Phone className="size-4" />
                Gọi
              </a>
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
