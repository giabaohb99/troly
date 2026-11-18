import { delay, http, HttpResponse } from 'msw'
import { calendarHandlers, calendarPending } from '@/mocks/calendar-handlers'
import { mockDb } from '@/mocks/db'
import { phase4Handlers } from '@/mocks/phase4-handlers'
import type { ChatAction, ChatMessage } from '@/modules/chat/types/chat'
import type { InboxMessage } from '@/modules/inbox/types/inbox'
import { parseMoney } from '@/shared/utils/format'

// API giả theo 12-api.md, đủ cho Phase 1: đăng nhập, chat SSE, hành động, chi tiêu, tìm, bản APK, client-logs.

const API = '/api/v1'
const ok = <T>(data: T, status = 200) => HttpResponse.json({ success: true, message: '', data }, { status })
const fail = (status: number, code: string, message: string) => HttpResponse.json({ success: false, message, data: { code } }, { status })
const tokens = () => ({
  access_token: `mock-access-${Date.now()}`,
  access_expires_at: new Date(Date.now() + 30 * 60_000).toISOString(),
  refresh_token: 'mock-refresh',
  refresh_expires_at: new Date(Date.now() + 365 * 86_400_000).toISOString(),
})
const user = { id: 1, name: 'Gia Bảo', email: 'giabao@example.com', timezone: 'Asia/Ho_Chi_Minh' }
const authed = (request: Request) => request.headers.get('Authorization')?.startsWith('Bearer mock-access-')
const nextId = () => ++mockDb.nextId

function message(role: ChatMessage['role'], text: string, extra: Partial<ChatMessage> = {}): ChatMessage {
  return { id: nextId(), role, text, model: null, citations: null, attachments: null, actions: null, status: 'done', created_at: new Date().toISOString(), ...extra }
}

function sse(events: { event: string; data: unknown; wait?: number }[]) {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    async start(controller) {
      for (const item of events) {
        await delay(item.wait ?? 120)
        controller.enqueue(encoder.encode(`event: ${item.event}\ndata: ${JSON.stringify(item.data)}\n\n`))
      }
      controller.close()
    },
  })
  return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' } })
}

function words(text: string) {
  return text.split(/(?<=\s)/).map((piece) => ({ event: 'text.delta', data: { text: piece }, wait: 40 }))
}

// Trả lời giả theo nội dung câu, mô phỏng đủ kiểu sự kiện và hành động.
// Tệp bot xuất (QĐ-41) trong chế độ giả.
const EXPORT_FILES: Record<string, { mime: string; ext: string }> = {
  pdf: { mime: 'application/pdf', ext: 'pdf' },
  word: { mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', ext: 'docx' },
  excel: { mime: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', ext: 'xlsx' },
}
export const mockFiles = new Map<number, { id: number; name: string; mime: string; size_bytes: number }>()

function planReply(text: string, mode: string) {
  const lower = text.toLowerCase()
  const exportKind = lower.includes('xuất') ? (['excel', 'word', 'pdf'].find((k) => lower.includes(k)) ?? 'pdf') : null
  if (exportKind) {
    const spec = EXPORT_FILES[exportKind]
    const file = { id: nextId(), name: `chi-tieu-thang-11.${spec.ext}`, mime: spec.mime, size_bytes: 48_000 }
    mockFiles.set(file.id, file)
    const actions: ChatAction[] = [{ id: 'a1', type: 'file', label: file.name, file_id: file.id, name: file.name, mime: file.mime, size_bytes: file.size_bytes }]
    // Như máy chủ: hành động file (hiện thẻ sớm khi đang chạy) và attachments của tin (thẻ chính, lịch sử).
    return { tool: { name: 'export_document', label: 'Đang xuất tệp' }, reply: `Em đã xuất chi tiêu tháng 11 ra tệp ${exportKind === 'excel' ? 'Excel' : exportKind === 'word' ? 'Word' : 'PDF'}.`, model: 'claude-haiku-5-5', actions, citations: null, attachments: [{ file_id: file.id, mime: file.mime, name: file.name, size_bytes: file.size_bytes }] }
  }
  const amount = parseMoney(lower.match(/(\d[\d.,]*\s*(k|tr|triệu|nghìn)?)\s*$/)?.[1] ?? '')
  if (amount && !lower.includes('xóa')) {
    const merchant = text.replace(/\d[\d.,]*\s*(k|tr|triệu|nghìn)?\s*$/i, '').trim() || 'Khoản chi'
    const id = nextId()
    mockDb.expenses.unshift({ id, amount_vnd: amount, kind: 'expense', account: 'cash', account_last4: null, to_account: null, to_account_last4: null, category: mockDb.categories[0], merchant, place: null, note: null, spent_at: new Date().toISOString(), source: 'chat', parser: 'chat', parse_confidence: null, needs_review: false, deleted: false })
    const actions: ChatAction[] = [
      { id: 'a1', type: 'open_screen', label: 'Sửa khoản này', screen: 'expense_detail', params: { expense_id: id } },
    ]
    return { tool: { name: 'add_expense', label: 'Đang ghi khoản chi' }, reply: `Ghi ${amount.toLocaleString('vi-VN')} đ ${merchant.toLowerCase()}, ăn uống.`, model: 'claude-haiku-5-5', actions, citations: null }
  }
  if (lower.includes('xóa')) {
    const victims = mockDb.expenses.filter((e) => !e.deleted).slice(0, 2)
    const pending = { id: nextId(), tool_name: 'delete_expenses', title: `Xóa ${victims.length} khoản chi`, summary: 'Xóa hàng loạt cần bấm duyệt.', details: victims.map((e) => ({ label: e.merchant ?? 'Khoản', value: `${e.amount_vnd.toLocaleString('vi-VN')} đ` })), danger: true, status: 'pending' as const, expires_at: new Date(Date.now() + 24 * 3_600_000).toISOString(), created_at: new Date().toISOString() }
    mockDb.pending.push(pending)
    const actions: ChatAction[] = [{ id: 'a1', type: 'confirm', label: pending.title, pending_action_id: pending.id, title: pending.title, summary: pending.summary, details: pending.details, confirm_label: 'Xóa', cancel_label: 'Bỏ', danger: true, expires_at: pending.expires_at }]
    return { tool: { name: 'delete_expenses', label: 'Đang chuẩn bị xóa' }, reply: 'Em chuẩn bị xóa hai khoản này, bấm Xóa để làm.', model: 'claude-haiku-5-5', actions, citations: null }
  }
  if (mode === 'research' || lower.includes('giá vàng')) {
    return {
      tool: { name: 'web_search', label: 'Đang tìm trên web' },
      reply: 'Giá vàng SJC sáng nay: mua 92,1 triệu, bán 94,1 triệu một lượng [1]. Vàng nhẫn thấp hơn khoảng 1,5 triệu [2].',
      model: 'claude-sonnet-5-5',
      actions: [] as ChatAction[],
      citations: [
        { title: 'Giá vàng SJC hôm nay', url: 'https://sjc.com.vn' },
        { title: 'Bảng giá vàng', url: 'https://vnexpress.net/chu-de/gia-vang-1403' },
      ],
    }
  }
  if (lower.includes('nhớ')) {
    mockDb.profile.version += 1
    const actions: ChatAction[] = [{ id: 'a1', type: 'memory_changed', label: 'Hoàn tác', version: mockDb.profile.version, text: text.replace(/^.*nhớ\s*/i, ''), undo_version: mockDb.profile.version - 1 }]
    return { tool: { name: 'remember', label: 'Đang ghi nhớ' }, reply: 'Em nhớ rồi.', model: 'claude-haiku-5-5', actions, citations: null }
  }
  const options: ChatAction[] = lower.includes('chọn')
    ? [{ id: 'a1', type: 'choices', label: 'Chọn', options: [{ label: 'Tháng này', value: 'Tổng chi tháng này' }, { label: 'Tuần này', value: 'Tổng chi tuần này' }] }]
    : []
  return {
    tool: null,
    reply: mode === 'think' ? `Em nghĩ kỹ rồi: **${text}** cần xem theo ba ý. Thứ nhất, ... Thứ hai, ... Thứ ba, ...` : `Em nghe: ${text}`,
    model: mode === 'think' ? 'claude-sonnet-5-5' : 'claude-haiku-5-5',
    actions: options,
    citations: null,
  }
}

function inRange(iso: string, from: string | null, to: string | null) {
  const t = Date.parse(iso)
  return (!from || t >= Date.parse(from)) && (!to || t < Date.parse(to))
}


const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString()
const inboxRow = (id: number, app: InboxMessage['app'], key: string, sender: string, text: string | null, minutes: number, extra: Partial<InboxMessage> = {}): InboxMessage => ({
  id, source: 'notification', app, sender, conversation_key: key, conversation_title: null, is_group: false, subject: null,
  text: text ?? '(Nội dung bị ẩn)', hidden_content: text === null, posted_at: minutesAgo(minutes), status: 'new', importance: 'normal', importance_reason: null, ...extra,
})
const mockInbox: InboxMessage[] = [
  inboxRow(1, 'zalo', 'zalo:lan', 'Chị Lan', 'Chiều nay họp lúc 3h nha em', 50, { importance: 'important', importance_reason: 'Người quan trọng' }),
  inboxRow(2, 'zalo', 'zalo:lan', 'Chị Lan', 'Nhớ mang bản in hợp đồng', 45, { importance: 'important', importance_reason: 'Người quan trọng' }),
  inboxRow(3, 'telegram', 'telegram:du-an-a', 'Tuấn', 'file mới đã up', 120, { conversation_title: 'Nhóm Dự án A', is_group: true }),
  inboxRow(4, 'zalo', 'zalo:hung', 'Anh Hùng', null, 300),
  inboxRow(5, 'sms', 'sms:me', 'Mẹ', 'Tối về ăn cơm nhé con', 2000, { status: 'seen' }),
]
function mockConversations() {
  const keys = [...new Set(mockInbox.map((m) => m.conversation_key))]
  return keys.map((key) => {
    const rows = mockInbox.filter((m) => m.conversation_key === key).sort((a, b) => Date.parse(b.posted_at) - Date.parse(a.posted_at))
    const last = rows[0]
    return {
      conversation_key: key, app: last.app, title: last.conversation_title ?? last.sender, is_group: last.is_group, last_sender: last.sender, last_text: last.text,
      last_posted_at: last.posted_at, unread_count: rows.filter((m) => m.status === 'new').length,
      importance: rows.some((m) => m.importance === 'important' && m.status !== 'done') ? 'important' : 'normal', is_private: false,
    }
  }).sort((a, b) => Number(b.importance === 'important') - Number(a.importance === 'important') || Date.parse(b.last_posted_at) - Date.parse(a.last_posted_at))
}
const mockDevices = [
  { id: 1, name: 'Galaxy S25+', model: 'SM-S936B', app_version_name: '0.1.0', last_seen_at: new Date().toISOString() },
  { id: 2, name: 'Galaxy A52 cũ', model: 'SM-A525F', app_version_name: '0.0.1', last_seen_at: new Date(Date.now() - 20 * 86_400_000).toISOString() },
]
const mockListened = [
  { id: 1, package_name: 'com.VCB', label: 'Vietcombank', purpose: 'expense', parser: 'vcb', enabled: true, is_default: true },
  { id: 2, package_name: 'vn.com.techcombank.bb.app', label: 'Techcombank', purpose: 'expense', parser: 'tcb', enabled: true, is_default: true },
  { id: 3, package_name: 'com.mservice.momotransfer', label: 'MoMo', purpose: 'expense', parser: 'momo', enabled: true, is_default: true },
  { id: 4, package_name: 'com.zing.zalo', label: 'Zalo', purpose: 'inbox', parser: 'zalo', enabled: true, is_default: true },
  { id: 5, package_name: 'org.telegram.messenger', label: 'Telegram', purpose: 'inbox', parser: 'telegram', enabled: true, is_default: true },
  { id: 6, package_name: 'com.facebook.orca', label: 'Messenger', purpose: 'inbox', parser: 'messenger', enabled: false, is_default: true },
  { id: 7, package_name: 'sms_default', label: 'SMS', purpose: 'inbox', parser: 'sms', enabled: true, is_default: true },
]

export const handlers = [
  ...calendarHandlers,
  ...phase4Handlers,
  http.post(`${API}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string }
    await delay(300)
    if (body.password !== 'matkhau123') return fail(401, 'AUTH_INVALID_CREDENTIALS', 'Email hoặc mật khẩu không đúng.')
    return ok({ ...tokens(), user })
  }),
  http.post(`${API}/auth/refresh`, () => ok({ ...tokens(), user })),
  http.post(`${API}/auth/logout`, () => ok(null)),
  http.get(`${API}/auth/me`, ({ request }) => (authed(request) ? ok(user) : fail(401, 'AUTH_REQUIRED', 'Cần đăng nhập.'))),
  http.post(`${API}/devices`, () => ok({ device: { id: 1 }, device_token: 'dev_mock' }, 201)),
  http.get(`${API}/devices`, () => ok({ items: mockDevices })),
  http.delete(`${API}/devices/:id`, ({ params }) => {
    const index = mockDevices.findIndex((d) => d.id === Number(params.id))
    if (index >= 0) mockDevices.splice(index, 1)
    return ok(null)
  }),
  http.post(`${API}/client-logs`, async ({ request }) => {
    const body = (await request.json()) as { items: unknown[] }
    console.info('[mock] client-logs', body.items)
    return ok({ accepted: body.items.length })
  }),

  http.get(`${API}/chat/today`, () => ok({ conversation: { id: 52, local_date: new Date().toISOString().slice(0, 10) }, messages: mockDb.messages, next_cursor: null, pending_actions: mockDb.pending })),
  http.get(`${API}/chat/status`, () => ok({ models: null, today_usd: 0.04, month_usd: 1.84, monthly_warn_usd: 200, over_monthly_warning: false, cache_read_ratio_7d: 0.8 })),
  http.delete(`${API}/chat/conversations/:id`, () => {
    mockDb.messages = []
    return ok(null)
  }),
  http.post(`${API}/chat/messages`, async ({ request }) => {
    const body = (await request.json()) as { text: string; mode?: string; attachment_file_ids?: number[] }
    if (body.text.toLowerCase().includes('lỗi mạng')) return fail(502, 'AI_UNAVAILABLE', 'Trợ lý đang lỗi, thử lại sau.')
    const userMessage = message('user', body.text)
    const plan = planReply(body.text, body.mode ?? 'chat')
    const attachments = 'attachments' in plan ? (plan.attachments as ChatMessage['attachments']) : null
    const assistant = message('assistant', plan.reply, { model: plan.model, citations: plan.citations, actions: plan.actions, attachments })
    mockDb.messages.push(userMessage, assistant)
    return sse([
      { event: 'message.created', data: { user_message: userMessage, conversation_id: 52 } },
      ...(plan.tool ? [{ event: 'tool.started', data: plan.tool, wait: 200 }, { event: 'tool.finished', data: { name: plan.tool.name, ok: true }, wait: 700 }] : []),
      ...words(plan.reply),
      ...plan.actions.map((action) => ({ event: 'action', data: action })),
      { event: 'message.completed', data: { assistant_message: { id: assistant.id, model: plan.model, citations: plan.citations, attachments }, usage: { input_tokens: 3120, output_tokens: 24, cache_read_tokens: 2900, cost_usd: 0.0003 } } },
    ])
  }),
  http.post(`${API}/chat/actions/:id/approve`, async ({ params }) => {
    await delay(500)
    const calendar = calendarPending.get(Number(params.id))
    if (calendar) {
      if (calendar.action.status !== 'pending') return fail(409, 'ACTION_NOT_PENDING', 'Hành động này đã được xử lý.')
      calendar.run()
      calendar.action.status = 'done'
      return ok({ action: calendar.action, result_text: 'Đã lưu và gửi thư cho khách.' })
    }
    const action = mockDb.pending.find((p) => p.id === Number(params.id))
    if (!action || action.status !== 'pending') return fail(409, 'ACTION_NOT_PENDING', 'Hành động này đã được xử lý.')
    action.status = 'done'
    mockDb.expenses.filter((e) => !e.deleted).slice(0, 2).forEach((e) => (e.deleted = true))
    return ok({ action, result_text: 'Đã xóa 2 khoản.' })
  }),
  http.post(`${API}/chat/actions/:id/reject`, ({ params }) => {
    const calendar = calendarPending.get(Number(params.id))
    if (calendar) {
      calendar.action.status = 'rejected'
      return ok({ action: calendar.action })
    }
    const action = mockDb.pending.find((p) => p.id === Number(params.id))
    if (!action) return fail(404, 'NOT_FOUND', 'Không tìm thấy.')
    action.status = 'rejected'
    return ok({ action })
  }),
  http.post(`${API}/memory/profile/revisions/:version/restore`, ({ params }) => {
    mockDb.profile.version = Number(params.version)
    return ok(mockDb.profile)
  }),
  http.get(`${API}/memory/profile`, () => ok({ ...mockDb.profile, updated_by: 'user', updated_at: new Date().toISOString() })),
  http.put(`${API}/memory/profile`, async ({ request }) => {
    const body = (await request.json()) as { content: string; version: number }
    if (body.version !== mockDb.profile.version) return fail(409, 'CONFLICT', 'Hồ sơ vừa được sửa ở nơi khác, tải lại rồi sửa tiếp.')
    mockDb.profile = { content: body.content, version: body.version + 1 }
    return ok({ ...mockDb.profile, updated_by: 'user', updated_at: new Date().toISOString() })
  }),

  http.post(`${API}/files/upload-url`, () => ok({ file_id: nextId(), upload_url: '/mock-r2/upload', upload_headers: null, expires_at: new Date(Date.now() + 300_000).toISOString() })),
  http.put('/mock-r2/upload', () => new HttpResponse(null, { status: 200 })),
  http.get(`${API}/files/:id`, ({ params }) => {
    const file = mockFiles.get(Number(params.id))
    if (!file) return fail(404, 'NOT_FOUND', 'Không tìm thấy tệp.')
    return ok({ ...file, download_url: `/mock-files/${file.name}` })
  }),
  http.get('/mock-files/:name', ({ params }) => new HttpResponse(`Tệp giả ${String(params.name)}`, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } })),
  http.post(`${API}/files/:id/complete`, ({ params }) => ok({ id: Number(params.id), status: 'ready' })),

  http.get(`${API}/expenses/categories`, () => ok({ items: mockDb.categories })),
  http.get(`${API}/expenses/summary`, ({ request }) => {
    const url = new URL(request.url)
    const period = url.searchParams.get('period') ?? 'month'
    const start = new Date()
    start.setHours(0, 0, 0, 0)
    if (period === 'week') start.setDate(start.getDate() - ((start.getDay() + 6) % 7))
    if (period === 'month') start.setDate(1)
    const rows = mockDb.expenses.filter((e) => !e.deleted && Date.parse(e.spent_at) >= start.getTime())
    const sum = (kind: string) => rows.filter((e) => e.kind === kind).reduce((total, e) => total + e.amount_vnd, 0)
    return ok({ from: start.toISOString(), to: new Date().toISOString(), total_expense_vnd: sum('expense'), total_income_vnd: sum('income'), total_transfer_vnd: sum('transfer'), groups: [] })
  }),
  http.get(`${API}/expenses`, ({ request }) => {
    const url = new URL(request.url)
    const category = url.searchParams.get('category_id')
    const review = url.searchParams.get('needs_review')
    const items = mockDb.expenses
      .filter((e) => !e.deleted)
      .filter((e) => inRange(e.spent_at, url.searchParams.get('from'), url.searchParams.get('to')))
      .filter((e) => !category || String(e.category?.id) === category)
      .filter((e) => review === null || String(e.needs_review) === review)
      .sort((a, b) => Date.parse(b.spent_at) - Date.parse(a.spent_at))
    return ok({ items, next_cursor: null })
  }),
  http.post(`${API}/expenses`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>
    const expense = { id: nextId(), account_last4: null, to_account: null, to_account_last4: null, place: null, source: 'manual' as const, parser: 'manual', parse_confidence: null, needs_review: false, deleted: false, ...(body as object), category: mockDb.categories.find((c) => c.id === body.category_id) ?? null } as (typeof mockDb.expenses)[number]
    mockDb.expenses.unshift(expense)
    return ok(expense, 201)
  }),
  http.get(`${API}/expenses/:id`, ({ params }) => {
    const expense = mockDb.expenses.find((e) => e.id === Number(params.id) && !e.deleted)
    return expense ? ok(expense) : fail(404, 'NOT_FOUND', 'Không tìm thấy khoản này.')
  }),
  http.patch(`${API}/expenses/:id`, async ({ params, request }) => {
    const expense = mockDb.expenses.find((e) => e.id === Number(params.id))
    if (!expense) return fail(404, 'NOT_FOUND', 'Không tìm thấy khoản này.')
    const body = (await request.json()) as Record<string, unknown>
    Object.assign(expense, body, 'category_id' in body ? { category: mockDb.categories.find((c) => c.id === body.category_id) ?? null, needs_review: false } : {})
    return ok(expense)
  }),
  http.delete(`${API}/expenses/:id`, ({ params }) => {
    const expense = mockDb.expenses.find((e) => e.id === Number(params.id))
    if (expense) expense.deleted = true
    return ok(null)
  }),
  http.post(`${API}/expenses/:id/restore`, ({ params }) => {
    const expense = mockDb.expenses.find((e) => e.id === Number(params.id))
    if (expense) expense.deleted = false
    return ok(expense ?? null)
  }),


  http.get(`${API}/expenses/:id/source`, ({ params }) => {
    const expense = mockDb.expenses.find((e) => e.id === Number(params.id))
    if (!expense || expense.source !== 'bank_notification') return fail(404, 'NOT_FOUND', 'Không còn thông báo gốc.')
    return ok({ app_package: 'com.VCB', title: 'Vietcombank', text: `So du TK VCB xxxx${expense.account_last4 ?? '0000'} -${expense.amount_vnd.toLocaleString('en-US')} VND luc 18-11-2026 08:15:02. Ref MBVCB.8812345`, posted_at: expense.spent_at })
  }),

  http.get(`${API}/devices/listened-apps`, () => ok({ items: mockListened })),
  http.patch(`${API}/devices/listened-apps/:id`, async ({ params, request }) => {
    const app = mockListened.find((a) => a.id === Number(params.id))
    if (!app) return fail(404, 'NOT_FOUND', 'Không tìm thấy app trong danh sách nghe.')
    Object.assign(app, (await request.json()) as object)
    return ok(app)
  }),

  http.get(`${API}/inbox/conversations`, ({ request }) => {
    const url = new URL(request.url)
    const app = url.searchParams.get('app')
    const importance = url.searchParams.get('importance')
    const rows = mockConversations().filter((c) => (!app || c.app === app) && (!importance || c.importance === importance))
    return ok({ items: rows, next_cursor: null })
  }),
  http.get(`${API}/inbox/conversations/:key/messages`, ({ params }) => ok({ items: mockInbox.filter((m) => m.conversation_key === params.key), next_cursor: null })),
  http.post(`${API}/inbox/conversations/:key/mark`, async ({ params, request }) => {
    const { status } = (await request.json()) as { status: 'seen' | 'done' }
    const rows = mockInbox.filter((m) => m.conversation_key === params.key)
    rows.forEach((m) => (m.status = status))
    return ok({ updated: rows.length })
  }),

  http.get(`${API}/search`, async ({ request }) => {
    const url = new URL(request.url)
    const q = (url.searchParams.get('q') ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').toLowerCase()
    const plain = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase()
    await delay(200)
    const terms = q.split(/\s+/).filter(Boolean)
    const hit = (text: string) => terms.every((t) => plain(text).includes(t))
    const items = [
      ...mockDb.notes.filter((n) => hit(`${n.title} ${n.body}`)).map((n) => ({ source: 'note', id: n.id, title: n.title, rank: 0.6, snippet: n.body.replace(/(hợp đồng nhà)/i, '<b>$1</b>'), date: n.created_at, open: { screen: 'settings_profile', params: null } })),
      ...mockDb.messages.filter((m) => hit(m.text)).map((m) => ({ source: 'chat', id: m.id, title: 'Chat', rank: 0.4, snippet: m.text, date: m.created_at, open: { screen: 'chat', params: null } })),
      ...(hit('hop dong thue nha') ? [{ source: 'file', id: 77, title: 'hop-dong-thue.pdf', rank: 0.42, snippet: '... bên A cho thuê <b>nhà</b> số 15 ...', date: '2026-03-12T09:00:00+07:00', open: null }] : []),
    ]
    return ok({ items })
  }),

  http.get(`${API}/device/release`, ({ request }) => {
    const current = Number(new URL(request.url).searchParams.get('current_version_code') ?? 0)
    const latest = { version_code: 100, version_name: '0.1.0', download_url: 'https://assistant.baohuynh.io.vn/tai-app', sha256: 'abc', size_bytes: 9_000_000, notes: 'Bản đầu.', min_supported_version_code: 0 }
    return ok({ update_available: current < latest.version_code, required: false, latest })
  }),
]
