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
// Nội dung tệp người dùng tải lên trong chế độ giả (để xem trước ảnh).
const mockBlobs = new Map<number, Blob>()
// Việc chờ duyệt mà duyệt sẽ thất bại (đối tượng không còn).
const failingActions = new Set<number>()

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
  if (lower.includes('xóa chuyến')) {
    const pending = { id: nextId(), tool_name: 'delete_trip', title: 'Xóa chuyến Đà Lạt', summary: 'Xóa cả chuyến cần bấm duyệt.', details: [{ label: 'Chuyến', value: 'Đà Lạt cuối tuần' }], danger: true, status: 'pending' as const, expires_at: new Date(Date.now() + 24 * 3_600_000).toISOString(), created_at: new Date().toISOString() }
    mockDb.pending.push(pending)
    failingActions.add(pending.id)
    const actions: ChatAction[] = [{ id: 'a1', type: 'confirm', label: pending.title, pending_action_id: pending.id, title: pending.title, summary: pending.summary, details: pending.details, confirm_label: 'Xóa', cancel_label: 'Bỏ', danger: true, expires_at: pending.expires_at }]
    return { tool: { name: 'delete_trip', label: 'Đang chuẩn bị xóa' }, reply: 'Bấm Xóa để xóa chuyến.', model: 'claude-haiku-5-5', actions, citations: null }
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
  inboxRow(6, 'gmail', 'gmail:t-hopdong', 'Anh Minh', 'Em gửi trước thứ Năm giúp anh nhé, chị Lan cần chốt.', 90, { source: 'gmail', subject: 'Hợp đồng thuê văn phòng 2027', conversation_title: 'Hợp đồng thuê văn phòng 2027', account_email: 'giabao@gmail.com' }),
  inboxRow(20, 'zalo', 'zalo:u:84901', 'Anh Minh', 'Chiều nay 3h họp ở văn phòng mới nhé', 30, { source: 'zalo_bridge', conversation_title: 'Anh Minh', status: 'seen' }),
  inboxRow(21, 'zalo', 'zalo:u:84901', 'Gia Bảo', 'Dạ em tới đúng giờ', 28, { source: 'zalo_bridge', conversation_title: 'Anh Minh', status: 'seen', is_self: true, quote: { msg_id: 'm20', text: 'Chiều nay 3h họp ở văn phòng mới nhé' } }),
  inboxRow(22, 'zalo', 'zalo:u:84901', 'Anh Minh', null, 26, { source: 'zalo_bridge', conversation_title: 'Anh Minh', hidden_content: false, text: null, media: [{ type: 'image', name: 'so-do-van-phong.jpg', size: 120_000, mime: 'image/jpeg', status: 'done', file_id: 9101 }] }),
  inboxRow(23, 'zalo', 'zalo:u:84901', 'Anh Minh', 'Gửi nhầm', 25, { source: 'zalo_bridge', conversation_title: 'Anh Minh', recalled_at: new Date(Date.now() - 24 * 60_000).toISOString() }),
  inboxRow(24, 'zalo', 'zalo:u:84901', 'Anh Minh', 'Xem hợp đồng ở https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/view?usp=sharing, có gì gọi 0909 123 456', 20, { source: 'zalo_bridge', conversation_title: 'Anh Minh' }),
  inboxRow(25, 'zalo', 'zalo:g:5521', 'Tuấn', 'Mai đi Bến Tre mấy giờ mọi người?', 60, { source: 'zalo_bridge', conversation_title: 'Nhóm đi Bến Tre', is_group: true, status: 'seen' }),
  inboxRow(26, 'zalo', 'zalo:g:5521', 'Chị Lan', '6h sáng nha, tập trung cổng chợ', 55, { source: 'zalo_bridge', conversation_title: 'Nhóm đi Bến Tre', is_group: true, status: 'seen' }),
  inboxRow(10, 'gmail', 'gmail:t-hoadon', 'VNPT', 'Hóa đơn cước tháng 11 của quý khách là 220.000 đ, hạn thanh toán 30/11.', 120, { source: 'gmail', subject: 'Hóa đơn điện tử tháng 11', conversation_title: 'Hóa đơn điện tử tháng 11', account_email: 'bao.congviec@gmail.com', status: 'seen' }),
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
      account_email: (last as { account_email?: string }).account_email ?? null,
    }
    // Như máy chủ sau phản hồi 1.0.7: chỉ xếp theo tin mới nhất, quan trọng là cờ.
  }).sort((a, b) => Date.parse(b.last_posted_at) - Date.parse(a.last_posted_at))
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
  { id: 5, package_name: 'org.telegram.messenger', label: 'Telegram', purpose: 'inbox', parser: 'telegram', enabled: false, is_default: true },
  { id: 6, package_name: 'com.facebook.orca', label: 'Messenger', purpose: 'inbox', parser: 'messenger', enabled: false, is_default: true },
  { id: 7, package_name: 'sms_default', label: 'SMS', purpose: 'inbox', parser: 'sms', enabled: true, is_default: true },
]

// Phiên chat giả (QĐ-51): 52 là phiên chính dùng mockDb.messages.
const MAIN_SESSION = 52
interface MockSession { id: number; title: string | null; pinned: boolean; created_at: string; messages: ChatMessage[] }
const daysAgo = (d: number, h = 9) => new Date(Date.now() - d * 86_400_000 + (h - 9) * 3_600_000).toISOString()
const chatSessions = new Map<number, MockSession>([
  [MAIN_SESSION, { id: MAIN_SESSION, title: null, pinned: false, created_at: daysAgo(0), messages: [] }],
  [41, { id: 41, title: 'Lịch trình Bến Tre', pinned: true, created_at: daysAgo(6), messages: [
    { ...message('user', 'Lập lịch trình đi Bến Tre cuối tuần bằng xe máy'), id: 4101, created_at: daysAgo(6) },
    { ...message('assistant', 'Em đã lập chuyến Bến Tre 2 ngày, ghé Cồn Phụng và chợ nổi.'), id: 4102, created_at: daysAgo(6) },
  ] }],
  [47, { id: 47, title: 'Chi tiêu tháng 11', pinned: false, created_at: daysAgo(3), messages: [
    { ...message('user', 'Tháng này tiêu bao nhiêu rồi?'), id: 4701, created_at: daysAgo(3) },
    { ...message('assistant', 'Tháng 11 đã chi 8,4 triệu, ăn uống nhiều nhất.'), id: 4702, created_at: daysAgo(3) },
  ] }],
])
const messagesOf = (id: number): ChatMessage[] => (id === MAIN_SESSION ? mockDb.messages : (chatSessions.get(id)?.messages ?? []))
// Phản hồi 1.1.1: phiên chưa có tin chỉ hiện khi vừa tạo bằng POST trong 10 phút; /chat/today không tạo phiên.
const isFreshEmpty = (s: MockSession) => messagesOf(s.id).length === 0 && Date.now() - Date.parse(s.created_at) < 10 * 60_000
const isVisibleSession = (s: MockSession) => messagesOf(s.id).length > 0 || isFreshEmpty(s)
const latestVisibleSession = () =>
  [...chatSessions.values()].filter(isVisibleSession).sort((a, b) => Date.parse(sessionMeta(b).last_message_at ?? b.created_at) - Date.parse(sessionMeta(a).last_message_at ?? a.created_at))[0]
function sessionMeta(s: MockSession) {
  const msgs = messagesOf(s.id)
  const last = msgs[msgs.length - 1]
  return { id: s.id, title: s.title, title_source: s.title ? 'user' : null, pinned: s.pinned, started_at: s.created_at, last_message_at: last?.created_at ?? null, last_preview: last?.text.slice(0, 120) ?? null, summary: null, message_count: msgs.length, created_at: s.created_at, local_date: s.created_at.slice(0, 10) }
}
function sessionView(id: number) {
  const msgs = messagesOf(id)
  const latest = msgs.slice(-50)
  return { conversation: sessionMeta(chatSessions.get(id)!), messages: latest, next_cursor: msgs.length > 50 ? String(latest[0].id) : null, pending_actions: mockDb.pending }
}

// Zalo giả (QĐ-52): bắt đầu đã đăng nhập; localStorage troly.mock.zalo_out = 1 thì bắt đầu chưa đăng nhập.
const zalo = {
  state: (typeof localStorage !== 'undefined' && localStorage.getItem('troly.mock.zalo_out') ? 'logged_out' : 'logged_in') as string,
  account: { uid: '84900', name: 'Gia Bảo' } as { uid: string; name: string } | null,
  loginAt: 0,
}
// Ô vuông 1x1 điểm ảnh làm mã QR giả.
const ZALO_QR = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
// Ảnh trong tin Zalo giả (file 9101): ảnh PNG thật để màn hiện được.
mockFiles.set(9101, { id: 9101, name: 'so-do-van-phong.png', mime: 'image/png', size_bytes: 120_000 })
mockBlobs.set(9101, new Blob([Uint8Array.from(atob(ZALO_QR), (c) => c.charCodeAt(0))], { type: 'image/png' }))

export const handlers = [
  ...calendarHandlers,
  // Zalo qua bridge (QĐ-52): đăng nhập QR giả (quét sau 4 giây, đồng ý sau 7 giây), danh bạ, lấy tin cũ, gửi tin.
  http.get(`${API}/zalo/status`, () => {
    if (zalo.state === 'waiting_scan' && Date.now() - zalo.loginAt > 4_000) zalo.state = 'scanned'
    if (zalo.state === 'scanned' && Date.now() - zalo.loginAt > 7_000) Object.assign(zalo, { state: 'logged_in', account: { uid: '84900', name: 'Gia Bảo' } })
    const qr = zalo.state === 'waiting_scan' ? { qr_png_base64: ZALO_QR, qr_expires_at: new Date(zalo.loginAt + 60_000).toISOString() } : {}
    return ok({ state: zalo.state, account: zalo.account, last_event_at: new Date().toISOString(), ...qr })
  }),
  http.post(`${API}/zalo/login`, () => {
    if (zalo.state === 'logged_in') return fail(409, 'CONFLICT', 'Zalo đã đăng nhập.')
    Object.assign(zalo, { state: 'waiting_scan', loginAt: Date.now(), account: null })
    return ok({ state: 'waiting_scan', account: null, qr_png_base64: ZALO_QR, qr_expires_at: new Date(Date.now() + 60_000).toISOString() })
  }),
  http.post(`${API}/zalo/logout`, () => {
    Object.assign(zalo, { state: 'logged_out', account: null })
    return ok({ state: 'logged_out', account: null })
  }),
  http.get(`${API}/zalo/contacts`, () => {
    if (zalo.state !== 'logged_in') return fail(409, 'NOT_LOGGED_IN', 'Zalo chưa đăng nhập.')
    return ok({ items: [
      { thread_id: '84901', thread_type: 'user', name: 'Anh Minh', avatar: null, conversation_key: 'zalo:u:84901' },
      { thread_id: '84902', thread_type: 'user', name: 'Chị Lan', avatar: null, conversation_key: 'zalo:u:84902' },
      { thread_id: '5521', thread_type: 'group', name: 'Nhóm đi Bến Tre', avatar: null, conversation_key: 'zalo:g:5521' },
    ] })
  }),
  http.post(`${API}/zalo/conversations/:key/sync`, ({ params }) => {
    const key = String(params.key)
    if (!key.startsWith('zalo:g:')) return ok({ mode: 'requested' })
    mockInbox.push(inboxRow(nextId(), 'zalo', key, 'Tuấn', 'Tin cũ từ Zalo: nhớ mang áo mưa', 300, { source: 'zalo_bridge', conversation_title: 'Nhóm đi Bến Tre', is_group: true, status: 'seen' }))
    return ok({ mode: 'group_history', saved: 1 })
  }),
  http.post(`${API}/zalo/messages`, async ({ request }) => {
    const body = (await request.json()) as { conversation_key: string; text?: string; file_ids?: number[]; client_ref?: string }
    if (zalo.state !== 'logged_in') return fail(409, 'NOT_LOGGED_IN', 'Zalo chưa đăng nhập.')
    if (!/^zalo:[ug]:/.test(body.conversation_key)) return fail(400, 'VALIDATION_ERROR', 'Không phải hội thoại Zalo.')
    if (body.text?.includes('nhanh quá')) return HttpResponse.json({ success: false, message: 'Gửi quá nhanh.', data: { code: 'RATE_LIMITED', retry_after: 20 } }, { status: 429 })
    // Bridge báo lại tin của mình sau 2 giây.
    setTimeout(() => {
      const title = mockInbox.find((m) => m.conversation_key === body.conversation_key)?.conversation_title ?? null
      mockInbox.push(inboxRow(nextId(), 'zalo', body.conversation_key, 'Gia Bảo', body.text ?? null, 0, {
        source: 'zalo_bridge', conversation_title: title, status: 'seen', is_self: true, is_group: body.conversation_key.startsWith('zalo:g:'), hidden_content: false, text: body.text ?? null,
        media: body.file_ids?.map((id) => ({ type: 'image', name: mockFiles.get(id)?.name ?? 'anh.jpg', size: 1000, mime: 'image/jpeg', status: 'done', file_id: id })) ?? null,
      }))
    }, 2_000)
    return ok({ msg_ids: [`z${Date.now()}`], client_ref: body.client_ref ?? null, conversation_key: body.conversation_key })
  }),
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

  // Phiên chat đặt tên (QĐ-51 bước 1): /chat/today là phiên hoạt động gần nhất.
  http.get(`${API}/chat/today`, () => {
    const latest = latestVisibleSession()
    return ok(latest ? sessionView(latest.id) : { conversation: null, messages: [], next_cursor: null, pending_actions: mockDb.pending })
  }),
  http.get(`${API}/chat/conversations`, ({ request }) => {
    const q = (new URL(request.url).searchParams.get('q') ?? '').toLowerCase()
    const items = [...chatSessions.values()]
      .filter(isVisibleSession)
      .map((s) => sessionMeta(s))
      .filter((m) => !q || `${m.title ?? ''} ${messagesOf(m.id).map((x) => x.text).join(' ')}`.toLowerCase().includes(q))
      .sort((a, b) => Number(b.pinned) - Number(a.pinned) || Date.parse(b.last_message_at ?? b.started_at) - Date.parse(a.last_message_at ?? a.started_at))
    return ok({ items, next_cursor: null })
  }),
  http.post(`${API}/chat/conversations`, async ({ request }) => {
    const body = (await request.json().catch(() => ({}))) as { title?: string }
    const reuse = [...chatSessions.values()].find(isFreshEmpty)
    if (reuse) return ok(sessionMeta(reuse), 200)
    const id = nextId()
    chatSessions.set(id, { id, title: body.title?.trim() || null, pinned: false, created_at: new Date().toISOString(), messages: [] })
    return ok(sessionMeta(chatSessions.get(id)!), 201)
  }),
  http.get(`${API}/chat/conversations/:id`, ({ params }) => {
    const id = Number(params.id)
    return chatSessions.has(id) ? ok(sessionView(id)) : fail(404, 'NOT_FOUND', 'Không tìm thấy phiên.')
  }),
  http.patch(`${API}/chat/conversations/:id`, async ({ params, request }) => {
    const s = chatSessions.get(Number(params.id))
    if (!s) return fail(404, 'NOT_FOUND', 'Không tìm thấy phiên.')
    const body = (await request.json()) as { title?: string; pinned?: boolean }
    if (body.title !== undefined) s.title = body.title.trim().slice(0, 120) || null
    if (body.pinned !== undefined) s.pinned = body.pinned
    return ok(sessionMeta(s))
  }),
  http.get(`${API}/chat/conversations/:id/messages`, ({ params, request }) => {
    const url = new URL(request.url)
    const cursor = Number(url.searchParams.get('cursor')) || Infinity
    const limit = Number(url.searchParams.get('limit')) || 50
    const before = messagesOf(Number(params.id)).filter((m) => m.id < cursor)
    const items = before.slice(-limit)
    return ok({ items, next_cursor: before.length > limit && items.length ? String(items[0].id) : null })
  }),
  http.get(`${API}/chat/status`, () => ok({ models: null, today_usd: 0.04, month_usd: 1.84, monthly_warn_usd: 200, over_monthly_warning: false, cache_read_ratio_7d: 0.8 })),
  http.delete(`${API}/chat/conversations/:id`, ({ params }) => {
    const id = Number(params.id)
    if (id === MAIN_SESSION) mockDb.messages = []
    chatSessions.delete(id)
    return ok(null)
  }),
  http.post(`${API}/chat/messages`, async ({ request }) => {
    const body = (await request.json()) as { text: string; mode?: string; attachment_file_ids?: number[]; conversation_id?: number }
    // Không chỉ phiên: phiên hoạt động gần nhất; phiên chưa có tên thì đặt theo câu đầu (như máy chủ).
    const target = chatSessions.get(body.conversation_id ?? -1) ?? latestVisibleSession()
    if (body.text.toLowerCase().includes('lỗi mạng')) return fail(502, 'AI_UNAVAILABLE', 'Trợ lý đang lỗi, thử lại sau.')
    const userMessage = message('user', body.text, { attachments: body.attachment_file_ids?.length ? body.attachment_file_ids.map((id) => ({ file_id: id })) : null })
    const plan = planReply(body.text, body.mode ?? 'chat')
    const attachments = 'attachments' in plan ? (plan.attachments as ChatMessage['attachments']) : null
    const assistant = message('assistant', plan.reply, { model: plan.model, citations: plan.citations, actions: plan.actions, attachments })
    const sessionId = target?.id ?? MAIN_SESSION
    if (target && !target.title) target.title = body.text.trim().slice(0, 40) || null
    messagesOf(sessionId).push(userMessage, assistant)
    return sse([
      { event: 'message.created', data: { user_message: userMessage, conversation_id: sessionId } },
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
      // Như máy chủ: bấm lại thẻ đã quyết trả 200 kèm trạng thái và decided_at cũ, không làm lần hai.
      if (calendar.action.status !== 'pending') return ok({ action: calendar.action, result_text: 'Đã làm xong.' })
      calendar.run()
      Object.assign(calendar.action, { status: 'done', decided_at: new Date().toISOString() })
      return ok({ action: calendar.action, result_text: 'Đã lưu và gửi thư cho khách.' })
    }
    const action = mockDb.pending.find((p) => p.id === Number(params.id))
    if (!action) return fail(404, 'NOT_FOUND', 'Không tìm thấy việc chờ duyệt.')
    if (action.status !== 'pending') return ok({ action, result_text: action.status === 'done' ? 'Đã làm xong.' : (action.error ?? '') })
    if (failingActions.has(action.id)) {
      Object.assign(action, { status: 'failed', error: 'Chuyến này đã bị xóa trước đó.', decided_at: new Date().toISOString() })
      return ok({ action, result_text: 'Chuyến này đã bị xóa trước đó.' })
    }
    Object.assign(action, { status: 'done', decided_at: new Date().toISOString() })
    mockDb.expenses.filter((e) => !e.deleted).slice(0, 2).forEach((e) => (e.deleted = true))
    return ok({ action, result_text: 'Đã xóa 2 khoản.' })
  }),
  http.get(`${API}/chat/actions`, ({ request }) => {
    const wanted = (new URL(request.url).searchParams.get('status') ?? 'pending').split(',')
    return ok({ items: [...mockDb.pending, ...[...calendarPending.values()].map((c) => c.action)].filter((a) => wanted.includes(a.status)) })
  }),
  http.post(`${API}/chat/actions/:id/reject`, ({ params }) => {
    const calendar = calendarPending.get(Number(params.id))
    if (calendar) {
      calendar.action.status = 'rejected'
      return ok({ action: calendar.action })
    }
    const action = mockDb.pending.find((p) => p.id === Number(params.id))
    if (!action) return fail(404, 'NOT_FOUND', 'Không tìm thấy.')
    if (action.status !== 'pending') return fail(409, 'ACTION_NOT_PENDING', 'Hành động này đã được xử lý.')
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

  // Kiểm purpose như máy chủ thật (file/models.py PURPOSES); lệch là 400 giống thật.
  http.post(`${API}/files/upload-url`, async ({ request }) => {
    const body = (await request.json()) as { purpose?: string; original_name?: string; mime?: string; size_bytes?: number }
    const purposes = ['chat_attachment', 'voice', 'document', 'trip_source', 'trip_export', 'report_export', 'other']
    if (body.purpose !== undefined && !purposes.includes(body.purpose)) return fail(400, 'VALIDATION_ERROR', 'Dữ liệu không hợp lệ.')
    const id = nextId()
    mockFiles.set(id, { id, name: body.original_name ?? 'tep', mime: body.mime ?? 'application/octet-stream', size_bytes: body.size_bytes ?? 0 })
    return ok({ file_id: id, upload_url: `/mock-r2/upload/${id}`, upload_headers: null, expires_at: new Date(Date.now() + 300_000).toISOString() })
  }),
  http.put('/mock-r2/upload/:id', async ({ params, request }) => {
    mockBlobs.set(Number(params.id), await request.blob())
    return new HttpResponse(null, { status: 200 })
  }),
  http.get(`${API}/files/:id`, ({ params }) => {
    const file = mockFiles.get(Number(params.id))
    if (!file) return fail(404, 'NOT_FOUND', 'Không tìm thấy tệp.')
    return ok({ id: file.id, original_name: file.name, mime: file.mime, size_bytes: file.size_bytes, download_url: mockBlobs.has(file.id) ? `/mock-blobs/${file.id}` : `/mock-files/${file.name}` })
  }),
  http.get('/mock-blobs/:id', ({ params }) => {
    const blob = mockBlobs.get(Number(params.id))
    return blob ? new HttpResponse(blob, { headers: { 'Content-Type': blob.type || 'application/octet-stream' } }) : new HttpResponse(null, { status: 404 })
  }),
  http.get('/mock-files/:name', ({ params }) =>
    String(params.name).endsWith('.md')
      ? new HttpResponse('# Ghi chú họp\n\nChốt **giá thuê** trước *thứ Năm*.\n\n- Bản in hợp đồng\n- Góp ý điều khoản\n\n1. Gửi anh Minh\n2. Báo chị Lan\n\n> Nhớ mang dấu công ty.\n\nXem [mẫu](https://example.com/mau).', { headers: { 'Content-Type': 'text/markdown; charset=utf-8' } })
      : new HttpResponse(`Tệp giả ${String(params.name)}`, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } }),
  ),
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
    const account = url.searchParams.get('account_email')?.toLowerCase()
    const rows = mockConversations().filter(
      (c) => (!app || c.app === app) && (!importance || c.importance === importance) && (!account || c.app !== 'gmail' || c.account_email?.toLowerCase() === account),
    )
    const accounts = [...new Set(mockConversations().flatMap((c) => (c.account_email ? [c.account_email] : [])))].sort()
    return ok({ items: rows, next_cursor: null, accounts })
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

// Chế độ giả: window.__trolySeedChat(120) thêm tin cũ để thử tải trang cũ hơn.
if (typeof window !== 'undefined') {
  ;(window as unknown as { __trolySeedChat: (n: number) => void }).__trolySeedChat = (n: number) => {
    const old: ChatMessage[] = []
    for (let i = 0; i < n; i++) old.push(message(i % 2 ? 'assistant' : 'user', `Tin cũ số ${i + 1}`, { id: 100 + i }))
    mockDb.messages = [...old, ...mockDb.messages]
  }
}
