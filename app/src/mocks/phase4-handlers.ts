import { delay, http, HttpResponse } from 'msw'
import type { InboxRule, SettingValues } from '@/modules/setting/api/setting-api'
import type { MapLinks, Stop, Trip, TripBrief } from '@/modules/trip/types/trip'
import { toDateKey } from '@/shared/utils/format'

// API giả cho Phase 4: lịch trình (41), báo cáo, cài đặt đầy đủ. Dữ liệu chuyến theo tệp mẫu Phước Hải – Trà Vinh.

const API = '/api/v1'
const ok = <T>(data: T, status = 200) => HttpResponse.json({ success: true, message: '', data }, { status })
const fail = (status: number, code: string, message: string) => HttpResponse.json({ success: false, message, data: { code } }, { status })

const today = toDateKey(new Date())
const shift = (key: string, days: number) => new Date(Date.parse(`${key}T00:00:00Z`) + days * 86_400_000).toISOString().slice(0, 10)
const at = (key: string, time: string) => new Date(`${key}T${time}:00+07:00`).toISOString()
let nextId = 9000

function stop(id: number, dayNo: number, seq: number, title: string, extra: Partial<Stop>): Stop {
  return {
    id, day_no: dayNo, seq, title, category: 'tham_quan', role: 'main', parent_stop_id: null, source_url: null, time_text: null, planned_start: null, planned_end: null, approx: false, fixed: false, optional: false,
    stay_minutes: null, place_query: title, place_id: `place-${id}`, lat: 10.2 + id / 1000, lng: 106.3 + id / 1000, resolve_status: 'ok', phone: null, cost_note: null, note: null,
    leg_km: null, leg_minutes: null, ...extra,
  }
}

const start = today
const trip: Trip & { deleted?: boolean } = {
  id: 1,
  title: 'Phước Hải – Trà Vinh',
  start_date: start,
  end_date: shift(start, 2),
  travel_mode: 'motorbike',
  origin_text: 'Phước Hải',
  status: 'planned',
  error: null,
  chosen_option_id: 11,
  start_date_suggested: true,
  advice: ['Đổ đầy xăng ở Bến Tre trước khi qua cầu Cổ Chiên.', 'Gọi hotline phà trước 16:00 để chắc chuyến cuối.'],
  notes: ['Mang áo mưa, kem chống nắng.'],
  days: [
    {
      day_no: 1, date: start, weekday_text: null, title: 'Phước Hải đi Bến Tre', total_km: 168, ride_minutes: 290,
      stops: [
        stop(101, 1, 1, 'Phước Hải', { category: 'khac', time_text: '5h30', planned_start: at(start, '05:30') }),
        stop(102, 1, 2, 'Phà Vũng Tàu – Cần Giờ', { category: 'pha', planned_start: at(start, '06:30'), fixed: true, leg_km: 38, leg_minutes: 55 }),
        stop(103, 1, 3, 'Bún nước lèo Cô Ba', { category: 'an_uong', planned_start: at(start, '08:30'), leg_km: 85, leg_minutes: 130, phone: '0909 123 456', cost_note: 'Khoảng 40k một tô' }),
        stop(104, 1, 4, 'Quán cơm tấm gần chợ', { category: 'an_uong', role: 'alternative', parent_stop_id: 103, place_query: 'cơm tấm chợ Bến Tre' }),
        stop(105, 1, 5, 'Cồn Phụng', { planned_start: at(start, '10:30'), leg_km: 22, leg_minutes: 40, lat: null, lng: null, place_id: null, resolve_status: 'uncertain' }),
        stop(106, 1, 6, 'Khách sạn Việt Úc', { category: 'khach_san', planned_start: at(start, '14:00'), leg_km: 23, leg_minutes: 45, fixed: true }),
      ],
    },
    {
      day_no: 2, date: shift(start, 1), weekday_text: null, title: 'Bến Tre đi Trà Vinh', total_km: 72, ride_minutes: 150,
      stops: [
        stop(201, 2, 1, 'Phà Cổ Chiên', { category: 'pha', planned_start: at(shift(start, 1), '10:00'), fixed: true, leg_km: 40, leg_minutes: 70 }),
        stop(202, 2, 2, 'Ao Bà Om', { planned_start: at(shift(start, 1), '13:00'), leg_km: 32, leg_minutes: 80, lat: null, lng: null, place_id: null, place_query: 'Ao Bà Om, Trà Vinh', resolve_status: 'not_found' }),
        stop(203, 2, 3, 'Bảo tàng Văn hóa Khmer', { planned_start: at(shift(start, 1), '15:00'), leg_km: 1, leg_minutes: 5, optional: true }),
      ],
    },
    { day_no: 3, date: shift(start, 2), weekday_text: null, title: 'Về', total_km: 210, ride_minutes: 330, stops: [stop(301, 3, 1, 'Chùa Âng', { planned_start: at(shift(start, 2), '07:00') }), stop(302, 3, 2, 'Phước Hải', { category: 'khac', planned_start: at(shift(start, 2), '16:00'), leg_km: 210, leg_minutes: 330 })] },
  ],
  needs_confirmation: [
    {
      stop_id: 105, day_no: 1, title: 'Cồn Phụng', place_query: 'Cồn Phụng Bến Tre',
      candidates: [
        { name: 'Khu du lịch Cồn Phụng', address: 'Tân Thạch, Châu Thành, Bến Tre', place_id: 'cp-1' },
        { name: 'Đạo Dừa Cồn Phụng', address: 'Tân Thạch, Châu Thành, Bến Tre', place_id: 'cp-2' },
      ],
    },
  ],
  facts: [
    { id: 1, kind: 'ferry_last', day_no: 2, stop_id: 201, value_time: '18:30:00', value_text: null, text: 'Chuyến cuối 18:30' },
    { id: 2, kind: 'checkin', day_no: 1, stop_id: 106, value_time: '14:00:00', value_text: null, text: 'Nhận phòng 14:00' },
  ],
  options: [
    { id: 11, name: 'Đúng giờ, ít rủi ro', summary: 'Rời Phước Hải sớm 30 phút, thêm một điểm nghỉ ở Mỏ Cày. Không còn rủi ro đỏ.', total_km: 450, total_ride_minutes: 770, night_ride_minutes: 0, red_count: 0, yellow_count: 2, changes: ['Rời sớm 30 phút ngày 1', 'Thêm nghỉ 20 phút ở Mỏ Cày'], chosen: true },
    { id: 12, name: 'Nhiều điểm', summary: 'Giữ đủ điểm như tệp; ngày 2 dễ trễ phà nếu nghỉ trưa lâu.', total_km: 462, total_ride_minutes: 800, night_ride_minutes: 35, red_count: 1, yellow_count: 3, changes: [], chosen: false },
    { id: 13, name: 'Nhàn', summary: 'Bỏ Bảo tàng Khmer, ở mỗi điểm lâu hơn; mỗi ngày dưới 6 giờ chạy.', total_km: 438, total_ride_minutes: 720, night_ride_minutes: 0, red_count: 0, yellow_count: 1, changes: ['Bỏ Bảo tàng Văn hóa Khmer'], chosen: false },
  ],
  evaluation: {
    evaluated_at: new Date().toISOString(),
    estimated: true,
    risks: [
      { code: 'R4', level: 'yellow', day_no: 1, stop_id: 103, message: 'Chạy liền 2 giờ 10 từ phà tới quán ăn', suggestion: 'Nghỉ 15 phút ở Mỏ Cày', checked_at: null },
      { code: 'R2', level: 'red', day_no: 2, stop_id: 203, message: 'Bảo tàng Văn hóa Khmer đóng cửa từ 16:00, tới 15:00 chỉ còn 60 phút', suggestion: 'Đi trước Ao Bà Om hoặc bỏ điểm này', checked_at: null },
      { code: 'R8', level: 'yellow', day_no: 1, stop_id: 105, message: 'Cồn Phụng chưa định vị', suggestion: 'Chọn đúng điểm ở mục cần xác nhận', checked_at: null },
    ],
  },
}

const importing: TripBrief = { id: 2, title: 'Đà Lạt cuối tuần', start_date: shift(today, 20), end_date: shift(today, 22), nights: 2, travel_mode: 'motorbike', status: 'importing', total_km: null, red_count: 0, yellow_count: 0, needs_confirmation_count: 0 }
const past: TripBrief = { id: 3, title: 'Long Hải', start_date: shift(today, -40), end_date: shift(today, -39), nights: 1, travel_mode: 'motorbike', status: 'done', total_km: 180, red_count: 0, yellow_count: 0, needs_confirmation_count: 0 }
let importPolls = 0

function brief(t: Trip): TripBrief {
  return {
    id: t.id, title: t.title, start_date: t.start_date, end_date: t.end_date, nights: 2, travel_mode: t.travel_mode, status: t.status,
    total_km: t.days.reduce((s, d) => s + (d.total_km ?? 0), 0), red_count: t.evaluation?.risks.filter((r) => r.level === 'red').length ?? 0,
    yellow_count: t.evaluation?.risks.filter((r) => r.level === 'yellow').length ?? 0, needs_confirmation_count: t.needs_confirmation.length,
  }
}

function mapLinks(dayNo: number, max: number): MapLinks {
  const stops = trip.days.find((d) => d.day_no === dayNo)?.stops.filter((s) => s.role === 'main' && s.lat !== null && s.lng !== null) ?? []
  const points = stops.map((s) => `${s.lat},${s.lng}`)
  const urls: string[] = []
  for (let i = 0; i < points.length - 1; i += max + 1) {
    const chunk = points.slice(i, i + max + 2)
    urls.push(`https://www.google.com/maps/dir/?api=1&origin=${chunk[0]}&destination=${chunk[chunk.length - 1]}&waypoints=${chunk.slice(1, -1).join('%7C')}&travelmode=two-wheeler&avoid=highways`)
  }
  return {
    day_no: dayNo,
    segments: [{ id: 'a1', type: 'open_map_directions', label: 'Xem đường cả ngày', urls, segment_labels: urls.map((_, i) => (urls.length > 1 ? `Xem đường cả ngày (${i + 1}/${urls.length})` : 'Xem đường cả ngày')) }],
    stops: stops.map((s) => ({
      stop_id: s.id, lat: s.lat as number, lng: s.lng as number,
      navigation: { id: `n${s.id}`, type: 'open_map_navigation', label: 'Dẫn đường', lat: s.lat, lng: s.lng, query: null, mode: 'l', avoid: 'h', fallback_url: `https://www.google.com/maps/dir/?api=1&destination=${s.lat},${s.lng}&travelmode=two-wheeler&dir_action=navigate` },
      place: { query: s.title, place_id: s.place_id },
    })),
  }
}

const settings: SettingValues = {
  'ui.voice_reply': false,
  'calendar.default_remind_minutes': [15],
  'calendar.week_start': 1,
  'expense.default_account': 'cash',
  'inbox.ai_enabled': true,
  'inbox.quiet_hours': null,
  'trip.default_travel_mode': 'motorbike',
  'trip.night_start': '18:00',
  'trip.night_end': '05:30',
  'trip.ride_break_minutes': 90,
  'trip.speed_factor': 1.2,
  'notify.new_transaction': false,
  'notify.important_message': true,
  'calendar.app_reminds_google': false,
  'trip.ferries': [{ name: 'Cát Lái', place_query: 'Bến phà Cát Lái', first_time: '04:00', last_time: '23:00', hotline: '028 3742 2222', note: null, updated_at: '2026-03-01' }],
}

const rules: InboxRule[] = [
  { id: 1, kind: 'vip_sender', value: 'Chị Lan', app: null, created_at: new Date().toISOString() },
  { id: 2, kind: 'urgent_keyword', value: 'gấp', app: null, created_at: new Date().toISOString() },
]

const revisions = [
  { version: 3, changed_by: 'user', reason: null, created_at: new Date(Date.now() - 2 * 86_400_000).toISOString(), preview: '# Hồ sơ lõi Tên: Gia Bảo. Ở TP.HCM. Đi xe máy.' },
  { version: 2, changed_by: 'assistant', reason: 'Ghi nhớ: đi xe máy, tránh cao tốc', created_at: new Date(Date.now() - 9 * 86_400_000).toISOString(), preview: '# Hồ sơ lõi Tên: Gia Bảo. Ở TP.HCM.' },
  { version: 1, changed_by: 'user', reason: null, created_at: new Date(Date.now() - 30 * 86_400_000).toISOString(), preview: 'Tên: Gia Bảo.' },
]

function aiCost() {
  const days = Number(today.slice(8))
  const byDay = Array.from({ length: days }, (_, i) => ({ date: `${today.slice(0, 8)}${String(i + 1).padStart(2, '0')}`, usd: Math.round((0.03 + ((i * 37) % 11) / 100) * 1000) / 1000 }))
  const total = Math.round(byDay.reduce((s, d) => s + d.usd, 0) * 100) / 100
  return {
    total_usd: total, today_usd: byDay[byDay.length - 1].usd, monthly_warn_usd: 200, by_day: byDay,
    by_model: [{ model: 'claude-haiku-5-5', usd: total * 0.55 }, { model: 'claude-sonnet-5-5', usd: total * 0.4 }, { model: 'claude-opus-5-5', usd: total * 0.05 }],
    by_purpose: [{ purpose: 'chat', usd: total * 0.6 }, { purpose: 'bank_extract', usd: total * 0.1 }, { purpose: 'trip_evaluate', usd: total * 0.2 }, { purpose: 'summary', usd: total * 0.1 }],
    cache_read_ratio: 0.82,
  }
}

export const phase4Handlers = [
  http.get(`${API}/trips`, () => {
    importPolls += 1
    if (importPolls > 3) importing.status = 'draft'
    return ok({ items: [...(trip.deleted ? [] : [brief(trip)]), importing, past], next_cursor: null })
  }),
  http.get(`${API}/trips/:id`, ({ params }) => (Number(params.id) === 1 && !trip.deleted ? ok(trip) : fail(404, 'NOT_FOUND', 'Không tìm thấy chuyến.'))),
  http.patch(`${API}/trips/:id`, async ({ request }) => {
    const { start_date } = (await request.json()) as { start_date?: string }
    if (start_date) {
      const offset = (Date.parse(`${start_date}T00:00:00Z`) - Date.parse(`${trip.start_date}T00:00:00Z`)) / 86_400_000
      trip.start_date = start_date
      trip.end_date = shift(start_date, trip.days.length - 1)
      for (const day of trip.days) {
        day.date = shift(start_date, day.day_no - 1)
        for (const s of day.stops) if (s.planned_start) s.planned_start = new Date(Date.parse(s.planned_start) + offset * 86_400_000).toISOString()
      }
      trip.start_date_suggested = false
    }
    return ok(trip)
  }),
  http.delete(`${API}/trips/:id`, () => {
    trip.deleted = true
    return ok(null)
  }),
  http.get(`${API}/trips/:id/map-links`, ({ request }) => {
    const url = new URL(request.url)
    return ok(mapLinks(Number(url.searchParams.get('day_no') ?? 1), Number(url.searchParams.get('max_waypoints') ?? 3)))
  }),
  http.post(`${API}/trips/:id/stops/:stopId/resolve`, async ({ request }) => {
    const { place_query } = (await request.json()) as { place_query: string }
    await delay(400)
    return ok({ candidates: [{ name: place_query, address: 'Bến Tre', place_id: `r-${place_query}`, lat: 10.24, lng: 106.37 }] })
  }),
  http.patch(`${API}/trips/:id/stops/:stopId`, async ({ params, request }) => {
    const body = (await request.json()) as Partial<Stop>
    const target = trip.days.flatMap((d) => d.stops).find((s) => s.id === Number(params.stopId))
    if (!target) return fail(404, 'NOT_FOUND', 'Không tìm thấy điểm.')
    // Chỉ có place_id thì máy chủ tự tra tọa độ.
    const coords = body.place_id && body.lat === undefined ? { lat: 10.33, lng: 106.36 } : {}
    Object.assign(target, body, coords, { resolve_status: body.resolve_status ?? 'manual' })
    trip.needs_confirmation = trip.needs_confirmation.filter((n) => n.stop_id !== target.id)
    if (trip.evaluation) trip.evaluation.risks = trip.evaluation.risks.filter((r) => !(r.code === 'R8' && r.stop_id === target.id))
    return ok(target)
  }),
  http.post(`${API}/trips/:id/evaluate`, () => {
    trip.status = 'evaluating'
    setTimeout(() => (trip.status = 'planned'), 6_000)
    return ok({ job_id: 77 }, 202)
  }),
  http.post(`${API}/trips/:id/options/:optionId/choose`, ({ params }) => {
    const id = Number(params.optionId)
    trip.options.forEach((o) => (o.chosen = o.id === id))
    trip.chosen_option_id = id
    return ok(trip)
  }),
  http.post(`${API}/trips/:id/to-calendar`, async () => {
    await delay(400)
    return ok({ event_ids: [1, 2, 3, 4, 5] })
  }),
  http.post(`${API}/trips/:id/export-docx`, async () => {
    await delay(600)
    return ok({ file_id: 88, download_url: 'https://example.com/lich-trinh.docx' })
  }),

  http.get(`${API}/reports/dashboard`, ({ request }) => {
    const date = new URL(request.url).searchParams.get('date') ?? today
    return ok({
      date,
      cards: {
        expense: { status: 'ok', data: { period: today.slice(0, 7), total_vnd: 4_820_000, previous_total_vnd: 5_300_000, income_vnd: 25_000_000, top_categories: [{ name: 'Ăn uống', total_vnd: 2_100_000 }, { name: 'Đi lại', total_vnd: 1_150_000 }, { name: 'Mua sắm', total_vnd: 890_000 }, { name: 'Hóa đơn', total_vnd: 480_000 }, { name: 'Khác', total_vnd: 200_000 }] }, message: null },
        calendar: { status: 'ok', data: { week_events: 9, next_event: { id: 202, title: 'Gọi khách A', start_at: at(today, '15:00') } }, message: null },
        tasks: { status: 'ok', data: { overdue: 1, today: 2, open: 6 }, message: null },
        inbox: { status: 'ok', data: { important_unseen: 2, new_count: 4 }, message: null },
        ai: { status: 'ok', data: { month_usd: aiCost().total_usd, today_usd: aiCost().today_usd, monthly_warn_usd: 200 }, message: null },
        devices: { status: 'error', data: null, message: 'Chưa đọc được trạng thái thiết bị, thử lại sau.' },
        health: { status: 'disabled', data: null, message: 'Có ở bản V2.' },
      },
    })
  }),
  http.get(`${API}/reports/ai-cost`, () => ok(aiCost())),

  http.get(`${API}/settings`, () => ok({ values: settings, defaults: settings })),
  http.patch(`${API}/settings`, async ({ request }) => {
    const changes = (await request.json()) as Partial<SettingValues>
    if (typeof changes['trip.speed_factor'] === 'number' && (changes['trip.speed_factor'] < 0.5 || changes['trip.speed_factor'] > 3)) {
      return HttpResponse.json({ success: false, message: 'Từ 0,5 tới 3.', data: { code: 'VALIDATION_ERROR', fields: { 'trip.speed_factor': 'Từ 0,5 tới 3.' } } }, { status: 422 })
    }
    Object.assign(settings, changes)
    return ok({ values: settings })
  }),
  http.get(`${API}/inbox/rules`, () => ok({ items: rules })),
  http.post(`${API}/inbox/rules`, async ({ request }) => {
    const body = (await request.json()) as Pick<InboxRule, 'kind' | 'value' | 'app'>
    const rule: InboxRule = { id: ++nextId, ...body, created_at: new Date().toISOString() }
    rules.push(rule)
    return ok(rule, 201)
  }),
  http.delete(`${API}/inbox/rules/:id`, ({ params }) => {
    const index = rules.findIndex((r) => r.id === Number(params.id))
    if (index >= 0) rules.splice(index, 1)
    return ok(null)
  }),
  http.get(`${API}/memory/profile/revisions`, () => ok({ items: revisions, next_cursor: null })),
  http.patch(`${API}/devices/:id`, async ({ params, request }) => {
    const { name } = (await request.json()) as { name: string }
    return ok({ id: Number(params.id), name, model: 'SM-S936B', app_version_name: '0.1.0', last_seen_at: new Date().toISOString() })
  }),
]
