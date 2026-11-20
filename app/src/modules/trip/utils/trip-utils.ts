import type { Risk, Stop, StopBooking, TripBrief } from '@/modules/trip/types/trip'
import { formatMoney, formatTime, toDateKey } from '@/shared/utils/format'

// "2 giờ 10", "45 phút".
export function formatDuration(minutes: number | null | undefined): string | null {
  if (minutes === null || minutes === undefined || minutes < 0) return null
  const m = Math.round(minutes)
  if (m < 60) return `${m} phút`
  const h = Math.floor(m / 60)
  const rest = m % 60
  return rest ? `${h} giờ ${String(rest).padStart(2, '0')}` : `${h} giờ`
}

// "85 km", "1,5 km".
export function formatKm(km: number | null | undefined): string | null {
  if (km === null || km === undefined) return null
  return `${km >= 10 ? Math.round(km) : km.toLocaleString('vi-VN', { maximumFractionDigits: 1 })} km`
}

// Rủi ro theo điểm, đỏ trước vàng.
export function risksByStop(risks: Risk[]): Map<number, Risk[]> {
  const map = new Map<number, Risk[]>()
  for (const risk of risks) {
    if (risk.stop_id === null) continue
    map.set(risk.stop_id, [...(map.get(risk.stop_id) ?? []), risk])
  }
  for (const list of map.values()) list.sort((a, b) => Number(b.level === 'red') - Number(a.level === 'red'))
  return map
}

// Gom điểm phụ ngay dưới điểm chính của nó, giữ thứ tự seq; điểm phụ không còn điểm chính thì đứng như điểm thường.
export function groupStops(stops: Stop[]): Stop[] {
  const sorted = [...stops].sort((a, b) => a.seq - b.seq)
  const ids = new Set(sorted.map((s) => s.id))
  const isChild = (s: Stop) => s.parent_stop_id !== null && ids.has(s.parent_stop_id)
  const result: Stop[] = []
  for (const stop of sorted) {
    if (isChild(stop)) continue
    result.push(stop, ...sorted.filter((s) => isChild(s) && s.parent_stop_id === stop.id))
  }
  return result
}

// Điểm có Dẫn đường: điểm chính hoặc đi qua. Không có tọa độ thì dẫn đường theo tên (QĐ-36).
export function canNavigate(stop: Stop): boolean {
  return stop.role === 'main' || stop.role === 'via'
}

type SearchFields = Pick<Stop, 'place_query' | 'title'> & Partial<Pick<Stop, 'area' | 'search_query'>>

// Chuỗi tìm một điểm trên Google Maps: chuỗi đầy đủ của máy chủ; không có thì tên kèm xã/phường, tỉnh (nếu tên chưa
// chứa). Không bao giờ tìm theo tên trần khi biết địa phương.
export function stopSearchText(stop: SearchFields): string {
  const full = stop.search_query?.trim()
  if (full) return full
  const name = (stop.place_query || stop.title || '').trim()
  const area = stop.area?.trim()
  if (!area) return name
  const fold = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase()
  return fold(name).includes(fold(area)) ? name : `${name}, ${area}`
}

export function navigationTarget(stop: Stop): { lat: number | null; lng: number | null; query: string | null } {
  if (stop.lat !== null && stop.lng !== null) return { lat: stop.lat, lng: stop.lng, query: null }
  return { lat: null, lng: null, query: stopSearchText(stop) }
}

// Chuyến đang đi đứng đầu, rồi chuyến sắp tới (gần nhất trước), rồi chuyến đã qua (mới nhất trước) (31 mục 3.5).
export function sortTrips(trips: TripBrief[], todayKey: string): TripBrief[] {
  const rank = (t: TripBrief) => {
    const start = t.start_date ?? '9999-12-31'
    const end = t.end_date ?? start
    if (start <= todayKey && todayKey <= end) return 0
    if (start > todayKey) return 1
    return 2
  }
  return [...trips].sort((a, b) => {
    const ra = rank(a)
    const rb = rank(b)
    if (ra !== rb) return ra - rb
    const sa = a.start_date ?? '9999-12-31'
    const sb = b.start_date ?? '9999-12-31'
    return ra === 2 ? sb.localeCompare(sa) : sa.localeCompare(sb)
  })
}

// Ngày mở mặc định: hôm nay nếu đang trong chuyến, không thì ngày 1.
export function defaultDayNo(days: { day_no: number; date: string | null }[], todayKey: string): number {
  return days.find((d) => d.date === todayKey)?.day_no ?? days[0]?.day_no ?? 1
}

// Chọn điểm để chỉ đường (1.0.2): Google Maps nhận tối đa 10 điểm một lần.
export const MAX_PICKED_STOPS = 10

// Điểm trong link như `_coord` của backend/app/modules/trip/links.py: tọa độ 6 chữ số, không có thì tên tìm.
export function stopCoord(stop: Pick<Stop, 'lat' | 'lng'> & SearchFields): string {
  if (stop.lat !== null && stop.lng !== null) return `${Number(stop.lat).toFixed(6)},${Number(stop.lng).toFixed(6)}`
  return stopSearchText(stop)
}

// Mã hóa như urlencode(quote_via=quote, safe=",|") của Python: giữ dấu phẩy và dấu |.
function encodeParam(value: string): string {
  return encodeURIComponent(value).replace(/%2C/gi, ',').replace(/%7C/gi, '|')
}

// Link chỉ đường các điểm đã chọn: không có origin (Google lấy vị trí hiện tại), destination là điểm cuối, waypoints
// là các điểm còn lại theo thứ tự trong lịch trình. Đây là đường chính (máy chủ không dựng link này).
export function pickedDirectionsUrl(stops: (Pick<Stop, 'lat' | 'lng'> & SearchFields)[]): string {
  const points = stops.map(stopCoord)
  const params: [string, string][] = [
    ['api', '1'],
    ['destination', points[points.length - 1]],
    ['travelmode', 'two-wheeler'],
    ['avoid', 'highways'],
  ]
  if (points.length > 1) params.push(['waypoints', points.slice(0, -1).join('|')])
  params.push(['dir_action', 'navigate'])
  return `https://www.google.com/maps/dir/?${params.map(([k, v]) => `${k}=${encodeParam(v)}`).join('&')}`
}

// Các điểm đã chọn xếp theo thứ tự trong lịch trình (không theo thứ tự bấm).
export function pickedInTripOrder(ordered: Stop[], picked: Set<number>): Stop[] {
  return ordered.filter((s) => picked.has(s.id))
}

export const TRAVEL_MODE_LABEL = { motorbike: 'Xe máy', car: 'Ô tô', walk: 'Đi bộ' } as const

// Giờ nhận, trả phòng: *14:00 21/11* (giờ Việt Nam). Thư không ghi giờ thì máy chủ để nửa đêm: chỉ hiện ngày.
export function formatBookingTime(iso: string | null): string | null {
  if (!iso || Number.isNaN(Date.parse(iso))) return null
  const [, m, d] = toDateKey(iso).split('-')
  const time = formatTime(iso)
  return time === '00:00' ? `${d}/${m}` : `${time} ${d}/${m}`
}

// Các dòng chữ của khối đặt chỗ trên một điểm khách sạn (QĐ-49).
export function bookingLines(b: StopBooking): { head: string; times: string | null; extra: string | null } {
  const head = [b.provider ? `Đặt qua ${b.provider}` : 'Đặt chỗ từ email', b.booking_ref ? `mã ${b.booking_ref}` : null].filter(Boolean).join(', ')
  const checkIn = formatBookingTime(b.check_in)
  const checkOut = formatBookingTime(b.check_out)
  const times = [checkIn ? `Nhận phòng ${checkIn}` : null, checkOut ? `Trả phòng ${checkOut}` : null].filter(Boolean).join(' · ') || null
  const amount = b.price === null || b.price === '' ? NaN : Number(b.price)
  const price = amount > 0 ? (b.currency && b.currency !== 'VND' ? `${amount.toLocaleString('vi-VN')} ${b.currency}` : formatMoney(amount)) : null
  const extra = [b.guests ? `${b.guests} khách` : null, price].filter(Boolean).join(' · ') || null
  return { head, times, extra }
}
