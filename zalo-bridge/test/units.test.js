import assert from 'node:assert/strict'
import { mkdtemp, readFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { EventQueue } from '../src/event-queue.js'
import { setLogLevel } from '../src/log.js'
import { mapContent, mapMessage, mapSeen, mapUndo } from '../src/mapper.js'
import { RateLimitError, SendLimiter } from '../src/send-limiter.js'
import { SessionStore, decrypt, encrypt } from '../src/session-store.js'
import { hostAllowed } from '../src/zalo-service.js'

setLogLevel('ERROR')
const KEY = Buffer.alloc(32, 7)

test('phiên mã hóa: giải mã đúng, sai khóa thì lỗi, tệp không chứa cookie rõ', async () => {
  const dir = await mkdtemp(path.join(tmpdir(), 'zb-'))
  const store = new SessionStore(dir, KEY)
  await store.save({ cookie: [{ key: 'zpw', value: 'bi-mat-cookie' }], imei: 'i', userAgent: 'u' })
  const raw = await readFile(path.join(dir, 'session.enc'))
  assert.equal(raw.includes(Buffer.from('bi-mat-cookie')), false)
  assert.equal((await store.load()).cookie[0].value, 'bi-mat-cookie')
  assert.throws(() => decrypt(Buffer.alloc(32, 8), encrypt(KEY, 'x')))
  await store.clear()
  assert.equal(await store.load(), null)
})

test('đổi nội dung tin theo loại', () => {
  assert.deepEqual(mapContent('webchat', 'chào'), { type: 'text', text: 'chào' })
  assert.equal(mapContent('chat.photo', { href: 'https://f.zdn.vn/a.jpg', thumb: 't' }).media.url, 'https://f.zdn.vn/a.jpg')
  const file = mapContent('share.file', { title: 'hd.pdf', href: 'h', params: '{"fileSize":"2048"}' })
  assert.deepEqual(file.media, { url: 'h', name: 'hd.pdf', size: 2048 })
  assert.equal(mapContent('chat.recommended', { href: 'https://x.vn', title: 'X' }).link.title, 'X')
  assert.deepEqual(mapContent('chat.sticker', { id: 5, catId: 9 }).sticker, { id: 5, cate_id: 9 })
  assert.equal(mapContent('chat.lạ', {}).type, 'other')
})

test('đổi tin, thu hồi, đã xem sang sự kiện', () => {
  const msg = mapMessage({
    type: 1, threadId: 'g1', isSelf: true,
    data: { msgId: '10', cliMsgId: '11', uidFrom: '0', dName: 'Tôi', ts: '1764040000000', msgType: 'webchat',
      content: 'hi', quote: { globalMsgId: 9, msg: 'trước' }, mentions: [{ uid: '2', pos: 0, len: 3 }] },
  })
  assert.equal(msg.event_id, 'msg:10')
  assert.equal(msg.thread_type, 'group')
  assert.equal(msg.is_self, true)
  assert.equal(msg.quote.msg_id, '9')
  assert.equal(msg.mentions[0].uid, '2')
  const undo = mapUndo({ threadId: '5', isSelf: false, isGroup: false, data: { msgId: '20', uidFrom: '5', ts: '1', content: { globalMsgId: 10 } } })
  assert.equal(undo.undo_msg_id, '10')
  assert.equal(undo.thread_type, 'user')
  const seen = mapSeen({ type: 1, threadId: 'g1', data: { msgId: '10', seenUids: ['2', '3'] } })
  assert.deepEqual(seen.seen_uids, ['2', '3'])
})

test('chỉ tải từ máy chủ được phép', () => {
  assert.equal(hostAllowed('https://abc.r2.cloudflarestorage.com/x', ['r2.cloudflarestorage.com']), true)
  assert.equal(hostAllowed('https://evil.com/x', ['r2.cloudflarestorage.com']), false)
  assert.equal(hostAllowed('file:///etc/passwd', ['zdn.vn']), false)
  assert.equal(hostAllowed('https://zdn.vn.evil.com/a', ['zdn.vn']), false)
})

test('hàng đợi sự kiện giữ lại khi api tắt, gửi khi api lên', async () => {
  const dir = await mkdtemp(path.join(tmpdir(), 'zb-'))
  let up = false
  const calls = []
  const fetchImpl = async (url, opts) => { calls.push(JSON.parse(opts.body)); return { ok: up, status: up ? 200 : 503 } }
  const timers = []
  const q = new EventQueue({ dataDir: dir, eventsUrl: 'http://api/x', token: 't', fetchImpl, setTimer: (fn, ms) => { timers.push(ms); return 1 }, clearTimer: () => {} })
  await q.push({ event_id: 'a' })
  assert.equal(await q.flush(), false)
  assert.equal(q.size, 1)
  const reloaded = new EventQueue({ dataDir: dir, eventsUrl: 'x', token: 't' })
  await reloaded.load()
  assert.equal(reloaded.size, 1)
  up = true
  q.timer = null
  assert.equal(await q.flush(), true)
  assert.equal(q.size, 0)
  assert.deepEqual(calls.at(-1).events.map((e) => e.event_id), ['a'])
})

test('giới hạn gửi: hàng chờ đầy thì từ chối, quá N tin mỗi phút thì chờ', async () => {
  let t = 0
  const slept = []
  const lim = new SendLimiter({ perMinute: 3, queueMax: 2, minGapMs: 0, maxGapMs: 1, now: () => t, sleep: async (ms) => { slept.push(ms); t += ms }, random: () => 0 })
  for (let i = 0; i < 3; i += 1) await lim.run(async () => i)
  await lim.run(async () => 'thu-4')
  assert.ok(slept.some((ms) => ms >= 59_000), 'tin thứ 4 phải chờ cửa sổ một phút')
  const blocker = new SendLimiter({ queueMax: 1, minGapMs: 0, maxGapMs: 1 })
  let release
  const first = blocker.run(() => new Promise((r) => { release = r }))
  await assert.rejects(() => blocker.run(async () => 1), RateLimitError)
  release('xong')
  assert.equal(await first, 'xong')
})

test('lô tối đa 100 sự kiện, xếp theo ts; api trả 200 có rejected thì bỏ; 401 thì dừng', async () => {
  const dir = await mkdtemp(path.join(tmpdir(), 'zb-'))
  const bodies = []
  let status = 200
  const fetchImpl = async (url, opts) => {
    bodies.push(JSON.parse(opts.body))
    return { ok: status < 300, status, json: async () => ({ success: true, data: { accepted: 1, rejected: [{ event_id: 'e1', reason: 'hong' }] } }) }
  }
  const q = new EventQueue({ dataDir: dir, eventsUrl: 'x', token: 't', fetchImpl, setTimer: () => 1, clearTimer: () => {} })
  for (let i = 0; i < 150; i += 1) q.items.push({ event_id: `e${i}`, ts: `2026-11-25T00:00:${String(59 - (i % 60)).padStart(2, '0')}Z` })
  assert.equal(await q.flush(), true)
  assert.equal(bodies.length, 2)
  assert.equal(bodies[0].events.length, 100)
  const ts = bodies[0].events.map((e) => e.ts)
  assert.deepEqual(ts, [...ts].sort())
  assert.equal(q.size, 0)
  status = 401
  q.items.push({ event_id: 'z', ts: '1' })
  assert.equal(await q.flush(), false)
  assert.equal(q.halted, true)
  assert.equal(q.size, 1)
  q.schedule(0)
  assert.equal(q.timer, null)
})

test('api trả 400 cho cả lô thì bỏ lô, không thử mãi', async () => {
  const dir = await mkdtemp(path.join(tmpdir(), 'zb-'))
  const q = new EventQueue({ dataDir: dir, eventsUrl: 'x', token: 't', fetchImpl: async () => ({ ok: false, status: 400 }), setTimer: () => 1, clearTimer: () => {} })
  q.items.push({ event_id: 'a', ts: '1' })
  assert.equal(await q.flush(), true)
  assert.equal(q.size, 0)
})
