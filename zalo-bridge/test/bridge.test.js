import assert from 'node:assert/strict'
import { mkdtemp, readFile, stat } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { EventQueue } from '../src/event-queue.js'
import { createApp } from '../src/http.js'
import { setLogLevel } from '../src/log.js'
import { SessionStore } from '../src/session-store.js'
import { ZaloService } from '../src/zalo-service.js'
import { makeFakeZalo } from './fake-zalo.js'

setLogLevel('ERROR')
const TOKEN = 'khoa-noi-bo-dai-it-nhat-24-ky-tu'
const KEY = Buffer.alloc(32, 3)

async function setup({ withSession = false } = {}) {
  const dir = await mkdtemp(path.join(tmpdir(), 'zb-'))
  const { FakeZalo, control } = makeFakeZalo()
  const events = []
  const queue = new EventQueue({ dataDir: dir, eventsUrl: 'http://api/x', token: TOKEN, setTimer: () => 1, clearTimer: () => {} })
  queue.push = async (e) => { events.push(e) }
  const store = new SessionStore(dir, KEY)
  if (withSession) await store.save({ cookie: [], imei: 'imei-1', userAgent: 'UA' })
  const fetched = []
  const fetchImpl = async (url) => {
    fetched.push(url)
    return { ok: true, headers: new Headers({ 'content-type': 'image/png', 'content-length': '4' }), arrayBuffer: async () => new Uint8Array([1, 2, 3, 4]).buffer }
  }
  const config = { userAgent: 'UA', sendPerMinute: 20, sendQueueMax: 5, attachmentHosts: ['r2.cloudflarestorage.com'] }
  // Hẹn giờ ngắn (chờ QR, chờ tin tự gửi) chạy ngay; hẹn dài (nối lại sau khi bị đá 10 phút) không chạy trong bài kiểm.
  const setTimer = (fn, ms) => { if (ms <= 60_000) setImmediate(fn); return 1 }
  const service = new ZaloService({ ZaloClass: FakeZalo, store, queue, config, fetchImpl, setTimer })
  service.limiter.minGapMs = 0
  service.limiter.maxGapMs = 1
  const server = createApp({ service, queue, token: TOKEN })
  await new Promise((r) => server.listen(0, '127.0.0.1', r))
  const base = `http://127.0.0.1:${server.address().port}`
  const call = (method, p, body, auth = true) => fetch(base + p, {
    method,
    headers: { 'content-type': 'application/json', ...(auth ? { authorization: `Bearer ${TOKEN}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  return { dir, control, events, service, server, call, fetched }
}

test('thiếu khóa thì 401, /health không cần khóa', async (t) => {
  const s = await setup()
  t.after(() => s.server.close())
  assert.equal((await s.call('GET', '/login/status', null, false)).status, 401)
  const h = await s.call('GET', '/health', null, false)
  assert.equal(h.status, 200)
  assert.equal((await h.json()).data.login_state, 'logged_out')
})

test('đăng nhập QR: có mã, quét, lưu phiên mã hóa, nghe tin và đẩy sự kiện', async (t) => {
  const s = await setup()
  t.after(() => s.server.close())
  const qr = await (await s.call('POST', '/login/qr')).json()
  assert.equal(qr.data.state, 'waiting_scan')
  assert.equal(qr.data.qr_png_base64, 'UVJQTkc=')
  s.control.scan()
  assert.equal(s.service.status().state, 'scanned')
  s.control.finish()
  await new Promise((r) => setTimeout(r, 20))
  const st = await (await s.call('GET', '/login/status')).json()
  assert.equal(st.data.state, 'logged_in')
  assert.deepEqual(st.data.account, { uid: '900100', name: 'Chủ tài khoản' })
  const raw = await readFile(path.join(s.dir, 'session.enc'))
  assert.equal(raw.includes(Buffer.from('bi-mat')), false)
  assert.equal(s.control.api.listener.started, 1)
  assert.equal((await s.call('POST', '/login/qr')).status, 409)

  s.control.api.listener.emit('message', {
    type: 0, threadId: '5', isSelf: false,
    data: { msgId: '77', cliMsgId: '78', uidFrom: '5', dName: 'Lan', ts: '1764040000000', msgType: 'webchat', content: 'Chiều họp nhé' },
  })
  await new Promise((r) => setTimeout(r, 20))
  const msg = s.events.find((e) => e.kind === 'message')
  assert.equal(msg.content.text, 'Chiều họp nhé')
  assert.equal(msg.thread_id, '5')
  assert.ok(s.events.some((e) => e.kind === 'session' && e.state === 'logged_in'))
})

test('khởi động có phiên đã lưu thì tự đăng nhập; bị đá thì báo kicked; đăng xuất xóa phiên', async (t) => {
  const s = await setup({ withSession: true })
  t.after(() => s.server.close())
  await s.service.init()
  assert.equal(s.service.state, 'logged_in')
  assert.equal(s.control.logins[0].imei, 'imei-1')
  s.control.api.listener.emit('closed', 3000, 'duplicate')
  assert.equal(s.service.state, 'kicked')
  await new Promise((r) => setImmediate(r))
  const out = await (await s.call('POST', '/logout')).json()
  assert.equal(out.data.state, 'logged_out')
  assert.equal(s.control.api.loggedOut, true)
  await assert.rejects(() => stat(path.join(s.dir, 'session.enc')))
})

test('gửi tin, tệp đính kèm, sticker; chặn địa chỉ tệp lạ; danh sách hội thoại', async (t) => {
  const s = await setup({ withSession: true })
  t.after(() => s.server.close())
  await s.service.init()
  const r1 = await (await s.call('POST', '/messages', { thread_id: '5', thread_type: 'user', text: 'Dạ', client_ref: 'c1' })).json()
  assert.deepEqual(r1.data, { msg_ids: ['111'], cli_msg_ids: [], client_ref: 'c1' })
  const r2 = await s.call('POST', '/messages', { thread_id: 'g1', thread_type: 'group', files: [{ url: 'https://acc.r2.cloudflarestorage.com/f.png', name: 'f.png' }] })
  assert.equal(r2.status, 200)
  const sentFile = s.control.api.sent.at(-1)
  assert.equal(sentFile.type, 1)
  assert.equal(sentFile.content.attachments[0].filename, 'f.png')
  assert.equal(sentFile.content.attachments[0].metadata.totalSize, 4)
  const bad = await (await s.call('POST', '/messages', { thread_id: '5', thread_type: 'user', files: [{ url: 'https://evil.com/x.exe', name: 'x.exe' }] })).json()
  assert.equal(bad.data.code, 'ATTACHMENT_HOST_NOT_ALLOWED')
  const st = await (await s.call('POST', '/messages', { thread_id: '5', thread_type: 'user', sticker: { id: 1, cate_id: 2 } })).json()
  assert.deepEqual(st.data.msg_ids, ['333'])
  const empty = await s.call('POST', '/messages', { thread_id: '5', thread_type: 'user' })
  assert.equal(empty.status, 400)
  const conv = await (await s.call('GET', '/conversations')).json()
  assert.deepEqual(conv.data.items.map((i) => i.thread_type), ['user', 'group'])
  const hist = await s.call('GET', '/conversations/5/messages?thread_type=user')
  assert.equal(hist.status, 400)
})

test('tải media chỉ từ máy chủ Zalo', async (t) => {
  const s = await setup({ withSession: true })
  t.after(() => s.server.close())
  await s.service.init()
  const bad = await s.call('POST', '/media/fetch', { url: 'http://169.254.169.254/latest' })
  assert.equal(bad.status, 400)
  const good = await s.call('POST', '/media/fetch', { url: 'https://f21-zpc.zdn.vn/a.jpg' })
  assert.equal(good.status, 200)
  assert.equal((await good.arrayBuffer()).byteLength, 4)
})

test('chưa đăng nhập thì gửi tin báo NOT_LOGGED_IN', async (t) => {
  const s = await setup()
  t.after(() => s.server.close())
  const r = await s.call('POST', '/messages', { thread_id: '5', thread_type: 'user', text: 'x' })
  assert.equal(r.status, 409)
  assert.equal((await r.json()).data.code, 'NOT_LOGGED_IN')
})

test('tin mình gửi qua bridge mang client_ref; tin có thread_name; bị đá thì không gửi được', async (t) => {
  const s = await setup({ withSession: true })
  t.after(() => s.server.close())
  await s.service.init()
  await (await s.call('POST', '/messages', { thread_id: '5', thread_type: 'user', text: 'Dạ', client_ref: 'c9' })).json()
  s.control.api.listener.emit('message', {
    type: 0, threadId: '5', isSelf: true,
    data: { msgId: '111', cliMsgId: '1', uidFrom: '0', dName: 'Tôi', ts: '1764040000000', msgType: 'webchat', content: 'Dạ' },
  })
  s.control.api.listener.emit('message', {
    type: 1, threadId: 'g1', isSelf: false,
    data: { msgId: '112', cliMsgId: '2', uidFrom: '7', dName: 'Hùng', ts: '1764040000001', msgType: 'webchat', content: 'Chào nhóm' },
  })
  await new Promise((r) => setTimeout(r, 30))
  const self = s.events.find((e) => e.kind === 'message' && e.msg_id === '111')
  assert.equal(self.client_ref, 'c9')
  assert.equal(self.thread_name, 'Lan')
  const group = s.events.find((e) => e.kind === 'message' && e.msg_id === '112')
  assert.equal(group.thread_name, 'Nhóm g1')
  assert.equal(group.client_ref, undefined)
  s.control.api.listener.emit('closed', 3003, 'kick')
  const r = await s.call('POST', '/messages', { thread_id: '5', thread_type: 'user', text: 'x' })
  assert.equal((await r.json()).data.code, 'NOT_LOGGED_IN')
})

test('quá hàng chờ gửi thì 429 kèm retry_after; media trả tên tệp', async (t) => {
  const s = await setup({ withSession: true })
  t.after(() => s.server.close())
  await s.service.init()
  s.service.limiter.queueMax = 0
  const r = await s.call('POST', '/messages', { thread_id: '5', thread_type: 'user', text: 'x' })
  assert.equal(r.status, 429)
  const body = await r.json()
  assert.equal(body.data.code, 'RATE_LIMITED')
  assert.ok(body.data.retry_after >= 1)
  assert.equal(r.headers.get('retry-after'), String(body.data.retry_after))
  const m = await s.call('POST', '/media/fetch', { url: 'https://f21-zpc.zdn.vn/x/anh%20chup.jpg' })
  assert.equal(m.headers.get('content-type'), 'image/png')
  assert.equal(decodeURIComponent(m.headers.get('x-file-name')), 'anh chup.jpg')
})
