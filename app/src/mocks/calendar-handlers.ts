import { http, HttpResponse } from 'msw'
import type { CalendarEvent, EventInput, Task, TaskInput } from '@/modules/calendar/types/calendar'
import type { OutboxItem } from '@/modules/setting/api/google-api'
import type { GoogleStatus } from '@/shared/hooks/use-google-status'
import type { PendingAction } from '@/shared/types/pending-action'
import { toDateKey } from '@/shared/utils/format'

// API giả cho Phase 3 (12 mục 5.5, 5.6): sự kiện (kể cả lần lặp, khách mời qua duyệt), việc, trạng thái Google.

const API = '/api/v1'
const ok = <T>(data: T, status = 200) => HttpResponse.json({ success: true, message: '', data }, { status })
const fail = (status: number, code: string, message: string) => HttpResponse.json({ success: false, message, data: { code } }, { status })

let nextId = 5000
const today = toDateKey(new Date())
const shift = (key: string, days: number) => new Date(Date.parse(`${key}T00:00:00Z`) + days * 86_400_000).toISOString().slice(0, 10)
const at = (key: string, time: string) => new Date(`${key}T${time}:00+07:00`).toISOString()

function makeEvent(id: number, title: string, extra: Partial<CalendarEvent>): CalendarEvent {
  return {
    id,
    occurrence_start: null,
    is_recurring: false,
    title,
    description: null,
    location: null,
    all_day: false,
    start_at: null,
    end_at: null,
    start_date: null,
    end_date: null,
    status: 'confirmed',
    remind_minutes: [],
    remind_source: 'app',
    is_alarm: false,
    attendees: [],
    source: 'app',
    task_id: null,
    sync_status: 'synced',
    google_html_link: null,
    is_organizer: true,
    ...extra,
  }
}

const self = { email: 'giabao@example.com', name: 'Gia Bảo', response_status: 'accepted', is_self: true }

const events: (CalendarEvent & { deleted?: boolean })[] = [
  makeEvent(201, 'Họp nhóm', {
    start_at: at(today, '09:00'),
    end_at: at(today, '10:00'),
    location: 'Phòng 3',
    remind_minutes: [15],
    attendees: [self, { email: 'lan@example.com', name: 'Chị Lan', response_status: 'accepted', is_self: false }, { email: 'tuan@example.com', name: 'Tuấn', response_status: 'needsAction', is_self: false }],
  }),
  makeEvent(202, 'Gọi khách A', { start_at: at(today, '15:00'), end_at: at(today, '15:30'), remind_source: 'google', source: 'google' }),
  makeEvent(203, 'Sinh nhật mẹ', { all_day: true, start_date: shift(today, 2), end_date: shift(today, 3), remind_minutes: [0], is_alarm: false }),
  makeEvent(204, 'Phỏng vấn đối tác', {
    start_at: at(shift(today, 1), '14:00'),
    end_at: at(shift(today, 1), '15:00'),
    remind_source: 'google',
    source: 'google',
    is_organizer: false,
    attendees: [self, { email: 'doitac@example.com', name: 'Đối tác', response_status: 'accepted', is_self: false }],
  }),
  makeEvent(205, 'Giờ phà Cần Thơ', { start_at: at(shift(today, 3), '05:30'), end_at: at(shift(today, 3), '06:00'), remind_minutes: [30], location: 'Bến phà' }),
  makeEvent(206, 'Gọi lại anh Hùng', { start_at: at(today, '17:00'), end_at: at(today, '17:15'), remind_minutes: [10], task_id: 105 }),
]

// Sự kiện lặp thứ Hai tới thứ Sáu, trải lần lặp như máy chủ.
function standups(from: string, to: string): CalendarEvent[] {
  const list: CalendarEvent[] = []
  for (let key = toDateKey(from); at(key, '00:00') < to; key = shift(key, 1)) {
    const weekday = new Date(`${key}T00:00:00Z`).getUTCDay()
    if (weekday === 0 || weekday === 6) continue
    const start = at(key, '08:30')
    list.push(makeEvent(300, 'Standup', { is_recurring: true, occurrence_start: start, start_at: start, end_at: at(key, '08:45'), remind_minutes: [5] }))
  }
  return list
}

const tasks: (Task & { deleted?: boolean })[] = [
  { id: 101, title: 'Nộp tờ khai thuế', note: null, status: 'todo', priority: 'high', due_date: shift(today, -1), due_at: null, completed_at: null, completed_source: null, event_id: null, sync_status: 'synced' },
  { id: 102, title: 'Gửi báo giá', note: null, status: 'todo', priority: 'high', due_date: today, due_at: null, completed_at: null, completed_source: null, event_id: null, sync_status: 'synced' },
  { id: 105, title: 'Gọi lại anh Hùng', note: null, status: 'todo', priority: 'normal', due_date: null, due_at: at(today, '17:00'), completed_at: null, completed_source: null, event_id: 206, sync_status: 'synced' },
  { id: 103, title: 'Mua quà sinh nhật mẹ', note: null, status: 'todo', priority: 'normal', due_date: shift(today, 1), due_at: null, completed_at: null, completed_source: null, event_id: null, sync_status: 'synced' },
  { id: 104, title: 'Đọc xong sách', note: null, status: 'todo', priority: 'low', due_date: null, due_at: null, completed_at: null, completed_source: null, event_id: null, sync_status: 'local_only' },
  { id: 106, title: 'Gia hạn tên miền', note: null, status: 'todo', priority: 'normal', due_date: shift(today, 5), due_at: null, completed_at: null, completed_source: null, event_id: null, sync_status: 'remote_deleted' },
  { id: 107, title: 'Đặt vé xe', note: null, status: 'done', priority: 'normal', due_date: shift(today, -2), due_at: null, completed_at: at(today, '07:00'), completed_source: 'google', event_id: null, sync_status: 'synced' },
]

const google: GoogleStatus = {
  connected: true,
  email: 'giabao@gmail.com',
  status: 'active',
  packs: [
    { name: 'calendar', enabled: true, granted: true, last_sync_at: new Date(Date.now() - 12 * 60_000).toISOString(), status: 'ok', last_error: null },
    { name: 'tasks', enabled: true, granted: true, last_sync_at: new Date(Date.now() - 20 * 60_000).toISOString(), status: 'ok', last_error: null },
  ],
  initial_sync: { state: 'done', message: '' },
  failed_outbox_count: 1,
}
const outbox: OutboxItem[] = [
  { id: 1, service: 'calendar', op: 'patch', local_type: 'event', local_id: 201, status: 'conflict', attempts: 1, last_error: null, has_discarded_change: true, updated_at: new Date().toISOString() },
]

// Việc chờ duyệt của lịch: duyệt thì chạy hàm đã lưu (handlers.ts gọi tới).
export const calendarPending = new Map<number, { action: PendingAction; run: () => void }>()

function pendingFor(title: string, summary: string, details: { label: string; value: string }[], run: () => void) {
  const action: PendingAction = { id: ++nextId, tool_name: 'add_event', title, summary, details, danger: false, status: 'pending', expires_at: new Date(Date.now() + 24 * 3_600_000).toISOString(), created_at: new Date().toISOString() }
  calendarPending.set(action.id, { action, run })
  return ok({ pending_action: action }, 202)
}

function applyInput(event: CalendarEvent, input: Partial<EventInput>) {
  const { attendees, ...rest } = input
  Object.assign(event, rest)
  if (attendees) event.attendees = [self, ...attendees.map((email) => ({ email, name: null, response_status: 'needsAction', is_self: false }))]
}

const guestsOf = (event: CalendarEvent) => event.attendees.filter((a) => !a.is_self)

// Gmail giả (QĐ-43): chưa cấp gói gmail thì 409 GOOGLE_NOT_CONNECTED như máy chủ.
const gmailReady = () => google.connected && google.packs.some((p) => p.name === 'gmail' && p.enabled)
const notConnected = () => fail(409, 'GOOGLE_NOT_CONNECTED', 'Chưa cấp quyền Gmail.')
const gmailThreads: Record<string, { thread_id: string; subject: string; account_email?: string; messages: { id: string; from_name: string | null; from_email: string; to: string[]; cc: string[]; date: string; text: string }[] }> = {
  't-hoadon': {
    thread_id: 't-hoadon',
    subject: 'Hóa đơn điện tử tháng 11',
    account_email: 'bao.congviec@gmail.com',
    messages: [{ id: 'h1', from_name: 'VNPT', from_email: 'hoadon@vnpt.vn', to: ['bao.congviec@gmail.com'], cc: [], date: at(today, '07:10'), text: 'Hóa đơn cước tháng 11 của quý khách là 220.000 đ, hạn thanh toán 30/11.' }],
  },
  't-hopdong': {
    thread_id: 't-hopdong',
    account_email: 'giabao@gmail.com',
    subject: 'Hợp đồng thuê văn phòng 2027',
    messages: [
      { id: 'm1', from_name: 'Anh Minh', from_email: 'minh@example.com', to: ['giabao@gmail.com'], cc: [], date: at(shift(today, -1), '09:15'), text: 'Chào em, anh gửi bản nháp hợp đồng thuê văn phòng năm 2027. Em xem giúp điều khoản giá nhé.' },
      { id: 'm2', from_name: 'Gia Bảo', from_email: 'giabao@gmail.com', to: ['minh@example.com'], cc: [], date: at(shift(today, -1), '10:02'), text: 'Dạ em nhận rồi, chiều nay em gửi lại góp ý.' },
      { id: 'm3', from_name: 'Anh Minh', from_email: 'minh@example.com', to: ['giabao@gmail.com'], cc: ['lan@example.com'], date: at(today, '08:30'), text: 'Em gửi trước thứ Năm giúp anh nhé, chị Lan cần chốt.' },
    ],
  },
}
let draftId = 7000
// Tài khoản Gmail thêm (QĐ-50): chỉ Gmail; tài khoản chính là tài khoản Google đang nối (id 1).
const mailAccounts: { id: number; email: string }[] = [{ id: 2, email: 'bao.congviec@gmail.com' }]
let nextAccountId = 3
function accountsView() {
  if (!google.connected) return []
  const primary = { id: 1, email: google.email ?? 'giabao@gmail.com', role: 'primary' as const, enabled_packs: google.packs.filter((p) => p.enabled).map((p) => p.name), status: google.status === 'reauth_required' ? ('reauth_required' as const) : ('active' as const), last_sync_at: new Date().toISOString(), last_error: null }
  return [primary, ...mailAccounts.map((a) => ({ ...a, role: 'mail' as const, enabled_packs: ['gmail'], status: 'active' as const, last_sync_at: new Date().toISOString(), last_error: null }))]
}
const drafts = new Map<number, { id: number; to: string[]; cc: string[]; subject: string; body: string; thread_ref: string | null; status: string; account_id?: number | null; account_email?: string | null }>()

export const calendarHandlers = [
  http.get(`${API}/gmail/threads/:id`, ({ params }) => {
    if (!gmailReady()) return notConnected()
    const thread = gmailThreads[String(params.id)]
    if (!thread) return fail(404, 'NOT_FOUND', 'Không tìm thấy luồng thư.')
    const last = thread.messages[thread.messages.length - 1]
    return ok({ ...thread, reply: { to: [last.from_email], cc: last.cc, subject: `Re: ${thread.subject}`, in_reply_to: last.id } })
  }),
  http.post(`${API}/gmail/drafts`, async ({ request }) => {
    if (!gmailReady()) return notConnected()
    const input = (await request.json()) as { to: string[]; cc: string[]; subject: string; body: string; thread_ref: string | null; account_id?: number | null }
    // QĐ-50: không chọn thì tài khoản của luồng thư, không thì tài khoản chính.
    const byThread = input.thread_ref ? gmailThreads[input.thread_ref]?.account_email : undefined
    const account = accountsView().find((a) => a.id === input.account_id) ?? accountsView().find((a) => a.email === byThread) ?? accountsView()[0]
    const draft = { id: ++draftId, ...input, account_id: account?.id ?? null, account_email: account?.email ?? null, status: 'draft' }
    drafts.set(draft.id, draft)
    return ok(draft, 201)
  }),
  http.post(`${API}/gmail/drafts/:id/send`, ({ params }) => {
    const draft = drafts.get(Number(params.id))
    if (!draft) return fail(404, 'NOT_FOUND', 'Không tìm thấy thư nháp.')
    return pendingFor(`Gửi thư: ${draft.subject || '(không tiêu đề)'}`, 'Thư chỉ đi khi bấm Duyệt.', [
      ...(draft.account_email ? [{ label: 'Gửi từ', value: draft.account_email }] : []),
      { label: 'Tới', value: draft.to.join(', ') },
      ...(draft.cc.length ? [{ label: 'Cc', value: draft.cc.join(', ') }] : []),
      { label: 'Nội dung', value: draft.body.slice(0, 300) },
    ], () => (draft.status = 'sent'))
  }),
  http.get(`${API}/calendar/events`, ({ request }) => {
    const url = new URL(request.url)
    const from = url.searchParams.get('from') ?? ''
    const to = url.searchParams.get('to') ?? ''
    const fromIso = new Date(from).toISOString()
    const toIso = new Date(to).toISOString()
    const inRange = (e: CalendarEvent) =>
      e.all_day ? `${e.end_date}T00:00` > fromIso.slice(0, 16) && `${e.start_date}T00:00` < toIso.slice(0, 16) : (e.end_at ?? '') > fromIso && (e.start_at ?? '') < toIso
    return ok({ items: [...events.filter((e) => !e.deleted && inRange(e)), ...standups(fromIso, toIso)] })
  }),
  http.get(`${API}/calendar/events/:id`, ({ params, request }) => {
    const id = Number(params.id)
    if (id === 300) {
      const occurrence = new URL(request.url).searchParams.get('occurrence_start') ?? at(today, '08:30')
      const occurrenceEvent = standups(occurrence, new Date(Date.parse(occurrence) + 60_000).toISOString())[0]
      return occurrenceEvent ? ok(occurrenceEvent) : fail(404, 'NOT_FOUND', 'Không tìm thấy sự kiện.')
    }
    const event = events.find((e) => e.id === id && !e.deleted)
    return event ? ok(event) : fail(404, 'NOT_FOUND', 'Không tìm thấy sự kiện.')
  }),
  http.post(`${API}/calendar/events`, async ({ request }) => {
    const input = (await request.json()) as EventInput
    const event = makeEvent(++nextId, input.title, {})
    applyInput(event, input)
    if (input.attendees.length > 0) {
      return pendingFor(`Gửi lời mời: ${input.title}`, 'Google sẽ gửi thư mời tới khách.', [{ label: 'Khách', value: input.attendees.join(', ') }], () => events.push(event))
    }
    events.push(event)
    return ok(event, 201)
  }),
  http.patch(`${API}/calendar/events/:id`, async ({ params, request }) => {
    const event = events.find((e) => e.id === Number(params.id) && !e.deleted)
    if (!event) return fail(404, 'NOT_FOUND', 'Không tìm thấy sự kiện.')
    const input = (await request.json()) as Partial<EventInput>
    const onlyRemind = Object.keys(input).every((k) => k.startsWith('remind') || k === 'is_alarm')
    if (event.is_organizer === false && !onlyRemind) return fail(403, 'FORBIDDEN', 'Sự kiện của người khác chỉ đổi được Ai nhắc.')
    const guests = input.attendees ?? guestsOf(event).map((a) => a.email)
    if (guests.length > 0 && !onlyRemind) {
      return pendingFor(`Cập nhật và báo khách: ${input.title ?? event.title}`, 'Google sẽ gửi thư cập nhật tới khách.', [{ label: 'Khách', value: guests.join(', ') }], () => applyInput(event, input))
    }
    applyInput(event, input)
    return ok(event)
  }),
  http.delete(`${API}/calendar/events/:id`, ({ params }) => {
    const event = events.find((e) => e.id === Number(params.id) && !e.deleted)
    if (!event) return fail(404, 'NOT_FOUND', 'Không tìm thấy sự kiện.')
    const guests = guestsOf(event)
    if (guests.length > 0 && event.is_organizer !== false) {
      return pendingFor(`Hủy và báo khách: ${event.title}`, 'Google sẽ gửi thư hủy tới khách.', [{ label: 'Khách', value: guests.map((g) => g.email).join(', ') }], () => (event.deleted = true))
    }
    event.deleted = true
    return ok(null)
  }),
  http.post(`${API}/calendar/events/:id/restore`, ({ params }) => {
    const event = events.find((e) => e.id === Number(params.id))
    if (!event) return fail(404, 'NOT_FOUND', 'Không tìm thấy sự kiện.')
    event.deleted = false
    return ok(event)
  }),

  http.get(`${API}/tasks`, ({ request }) => {
    const status = new URL(request.url).searchParams.get('status') ?? 'todo'
    return ok({ items: tasks.filter((t) => !t.deleted && status.split(',').includes(t.status)), next_cursor: null })
  }),
  http.get(`${API}/tasks/:id`, ({ params }) => {
    const task = tasks.find((t) => t.id === Number(params.id) && !t.deleted)
    return task ? ok(task) : fail(404, 'NOT_FOUND', 'Không tìm thấy việc.')
  }),
  http.post(`${API}/tasks`, async ({ request }) => {
    const input = (await request.json()) as TaskInput
    const task: Task = { id: ++nextId, ...input, status: 'todo', completed_at: null, completed_source: null, event_id: null, sync_status: 'pending' }
    tasks.push(task)
    return ok(task, 201)
  }),
  http.patch(`${API}/tasks/:id`, async ({ params, request }) => {
    const task = tasks.find((t) => t.id === Number(params.id) && !t.deleted)
    if (!task) return fail(404, 'NOT_FOUND', 'Không tìm thấy việc.')
    Object.assign(task, (await request.json()) as Partial<TaskInput>)
    return ok(task)
  }),
  http.delete(`${API}/tasks/:id`, ({ params }) => {
    const task = tasks.find((t) => t.id === Number(params.id))
    if (task) task.deleted = true
    return ok(null)
  }),
  http.post(`${API}/tasks/:id/restore`, ({ params }) => {
    const task = tasks.find((t) => t.id === Number(params.id))
    if (!task) return fail(404, 'NOT_FOUND', 'Không tìm thấy việc.')
    task.deleted = false
    return ok(task)
  }),
  http.post(`${API}/tasks/:id/complete`, ({ params }) => {
    const task = tasks.find((t) => t.id === Number(params.id) && !t.deleted)
    if (!task) return fail(404, 'NOT_FOUND', 'Không tìm thấy việc.')
    Object.assign(task, { status: 'done', completed_at: new Date().toISOString(), completed_source: 'app' })
    return ok(task)
  }),
  http.post(`${API}/tasks/:id/reopen`, ({ params }) => {
    const task = tasks.find((t) => t.id === Number(params.id) && !t.deleted)
    if (!task) return fail(404, 'NOT_FOUND', 'Không tìm thấy việc.')
    Object.assign(task, { status: 'todo', completed_at: null, completed_source: null })
    return ok(task)
  }),
  http.post(`${API}/tasks/:id/resolve-remote-delete`, async ({ params, request }) => {
    const task = tasks.find((t) => t.id === Number(params.id) && !t.deleted)
    if (!task) return fail(404, 'NOT_FOUND', 'Không tìm thấy việc.')
    const { keep } = (await request.json()) as { keep: boolean }
    if (!keep) {
      task.deleted = true
      return ok(null)
    }
    task.sync_status = 'pending'
    return ok(task)
  }),

  http.get(`${API}/google/status`, () => ok({ ...google, failed_outbox_count: google.connected ? outbox.length : 0 })),
  // Nhiều tài khoản Gmail (QĐ-50).
  http.get(`${API}/google/accounts`, () => ok({ items: accountsView() })),
  http.delete(`${API}/google/accounts/:id`, ({ params }) => {
    const id = Number(params.id)
    if (id === 1) return fail(409, 'CONFLICT', 'Đây là tài khoản chính, dùng Ngắt kết nối.')
    const i = mailAccounts.findIndex((a) => a.id === id)
    if (i < 0) return fail(404, 'NOT_FOUND', 'Không tìm thấy tài khoản.')
    mailAccounts.splice(i, 1)
    return ok({ ok: true })
  }),
  http.post(`${API}/google/connect`, async ({ request }) => {
    const { packs = [], role } = (await request.json()) as { packs?: ('calendar' | 'tasks' | 'gmail')[]; role?: 'mail' }
    if (role === 'mail') {
      const id = nextAccountId++
      mailAccounts.push({ id, email: `them${id}@gmail.com` })
      return ok({ auth_url: '/cai-dat/google?ket-qua=ok&tai-khoan=mail' })
    }
    Object.assign(google, { connected: true, status: 'active', initial_sync: { state: 'running', message: 'Đang lấy lịch và việc lần đầu.' } })
    google.packs = (['calendar', 'tasks', 'gmail'] as const).map((name) => ({ name, enabled: packs.includes(name) || google.packs.some((p) => p.name === name && p.enabled), granted: true, last_sync_at: null, status: 'ok', last_error: null }))
    setTimeout(() => {
      google.initial_sync = { state: 'done', message: '' }
      google.packs.forEach((p) => (p.last_sync_at = new Date().toISOString()))
    }, 5_000)
    // Trên trình duyệt giả lập việc máy chủ đưa về troly://cai-dat/google?ket-qua=ok.
    return ok({ auth_url: '/cai-dat/google?ket-qua=ok' })
  }),
  http.post(`${API}/google/disconnect`, () => {
    Object.assign(google, { connected: false, status: 'revoked', packs: [] })
    return ok(null)
  }),
  http.post(`${API}/google/sync/:service`, ({ params }) => {
    const pack = google.packs.find((p) => p.name === params.service)
    if (pack) pack.last_sync_at = new Date().toISOString()
    return ok({ queued: true }, 202)
  }),
  http.get(`${API}/google/outbox`, () => ok({ items: google.connected ? outbox : [] })),
  http.post(`${API}/google/outbox/:id/retry`, ({ params }) => {
    const index = outbox.findIndex((o) => o.id === Number(params.id))
    if (index < 0) return fail(404, 'NOT_FOUND', 'Không tìm thấy lệnh.')
    const [item] = outbox.splice(index, 1)
    return ok({ ...item, status: 'pending' })
  }),
]
