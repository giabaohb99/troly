// Lõi cầu nối: đăng nhập QR, giữ phiên, nghe tin, gửi tin, tra cứu (QĐ-52, 50 mục 3.15).
// Nhận ZaloClass qua tham số để bài kiểm thay bằng bản giả.
import { imageSize } from 'image-size'
import { hashId, log } from './log.js'
import {
  mapDelivered, mapMessage, mapReaction, mapSeen, mapUndo, sessionEvent, threadTypeValue,
} from './mapper.js'
import { SendLimiter } from './send-limiter.js'

const QR_TTL_MS = 100_000
const KICK_RETRY_MS = 10 * 60_000
const MAX_MEDIA_BYTES = 50 * 1024 * 1024
const ZALO_MEDIA_HOSTS = ['zdn.vn', 'zadn.vn', 'zalo.me', 'zaloapp.com']
const CLOSE_DUPLICATE = 3000
const CLOSE_KICK = 3003
const NAME_TTL_MS = 6 * 3600_000
const SENT_REF_TTL_MS = 10 * 60_000
const SELF_WAIT_MS = 5_000

export class BridgeError extends Error {
  constructor(code, message, status = 400) {
    super(message)
    Object.assign(this, { code, status })
  }
}

export function hostAllowed(url, hosts) {
  let u
  try {
    u = new URL(url)
  } catch {
    return false
  }
  if (!['https:', 'http:'].includes(u.protocol)) return false
  const h = u.hostname.toLowerCase()
  return hosts.some((allowed) => h === allowed || h.endsWith('.' + allowed))
}

export class ZaloService {
  constructor({ ZaloClass, store, queue, config, fetchImpl = fetch, limiter, setTimer = setTimeout, now = Date.now }) {
    Object.assign(this, { ZaloClass, store, queue, config, fetch: fetchImpl, setTimer, now })
    this.limiter = limiter || new SendLimiter({ perMinute: config.sendPerMinute, queueMax: config.sendQueueMax })
    this.state = 'logged_out'
    this.api = null
    this.qr = null
    this.qrExpiresAt = null
    this.scannedName = null
    this.account = null
    this.listenerUp = false
    this.qrAbort = null
    this.kickTimer = null
    this.lastError = null
    this.names = new Map() // "user:<id>" | "group:<id>" -> {name, at}
    this.sentRefs = new Map() // msgId -> {clientRef, at}
    this.inflight = new Map() // threadId -> Promise của lần gửi đang chạy
  }

  status() {
    const out = { state: this.state }
    if (this.state === 'waiting_scan' && this.qr) {
      out.qr_png_base64 = this.qr
      out.qr_expires_at = new Date(this.qrExpiresAt).toISOString()
    }
    if (this.state === 'scanned' && this.scannedName) out.scanned_name = this.scannedName
    if (this.account) out.account = this.account
    if (this.state === 'error' && this.lastError) out.error = this.lastError
    return out
  }

  newZalo() {
    return new this.ZaloClass({ selfListen: true, checkUpdate: false, logging: false })
  }

  // Khởi động: có phiên đã lưu thì đăng nhập lại và nghe tin.
  async init() {
    let creds
    try {
      creds = await this.store.load()
    } catch (err) {
      this.state = 'error'
      this.lastError = 'Không giải mã được phiên đã lưu; đăng nhập lại bằng QR.'
      log.error('Phiên Zalo đã lưu hỏng hoặc sai ZALO_SESSION_KEY', { error: err.message })
      return
    }
    if (!creds) return
    try {
      const api = await this.newZalo().login(creds)
      await this.onLoggedIn(api)
    } catch (err) {
      this.state = 'error'
      this.lastError = 'Phiên Zalo hết hạn hoặc bị từ chối; đăng nhập lại bằng QR.'
      log.error('Không đăng nhập lại được bằng phiên đã lưu', { error: err.message })
      await this.queue.push(sessionEvent('error'))
    }
  }

  async startQR() {
    if (this.state === 'logged_in') throw new BridgeError('ALREADY_LOGGED_IN', 'Đã đăng nhập Zalo.', 409)
    if (this.qrAbort) {
      try { this.qrAbort() } catch { /* bỏ qua */ }
    }
    this.qr = null
    this.scannedName = null
    let resolveReady
    const ready = new Promise((r) => { resolveReady = r })
    let credentials = null
    const zalo = this.newZalo()
    const loginPromise = zalo.loginQR({ userAgent: this.config.userAgent }, (event) => {
      switch (event.type) {
        case 0: // QRCodeGenerated
          this.qrAbort = event.actions?.abort ?? null
          this.qr = event.data.image
          this.qrExpiresAt = this.now() + QR_TTL_MS
          this.state = 'waiting_scan'
          resolveReady()
          break
        case 1: // QRCodeExpired
          this.state = 'expired'
          this.qr = null
          resolveReady()
          break
        case 2: // QRCodeScanned
          this.state = 'scanned'
          this.scannedName = event.data?.display_name || null
          break
        case 3: // QRCodeDeclined
          this.state = 'logged_out'
          this.qr = null
          break
        case 4: // GotLoginInfo
          credentials = { cookie: event.data.cookie, imei: event.data.imei, userAgent: event.data.userAgent }
          break
        default:
          break
      }
    })
    loginPromise
      .then(async (api) => {
        if (!api) return
        if (credentials) await this.store.save(credentials)
        this.qrAbort = null
        await this.onLoggedIn(api)
      })
      .catch((err) => {
        if (this.state === 'logged_in') return
        if (this.state !== 'expired' && this.state !== 'logged_out') {
          this.state = 'error'
          this.lastError = 'Đăng nhập QR không thành công.'
        }
        log.warn('Đăng nhập QR dừng', { error: err?.message })
        resolveReady()
      })
    await Promise.race([ready, new Promise((r) => this.setTimer(r, 20_000))])
    return this.status()
  }

  async onLoggedIn(api) {
    this.api = api
    this.qr = null
    this.lastError = null
    let name = ''
    try {
      name = (await api.fetchAccountInfo())?.profile?.displayName || ''
    } catch {
      /* tên không bắt buộc */
    }
    this.account = { uid: String(api.getOwnId()), name }
    this.state = 'logged_in'
    this.attachListener()
    log.info('Đã đăng nhập Zalo', { uid: hashId(this.account.uid) })
    await this.queue.push(sessionEvent('logged_in', { account: this.account }))
  }

  attachListener() {
    const l = this.api.listener
    const push = (event) => {
      log.info('Sự kiện Zalo', { kind: event.kind, thread: hashId(event.thread_id), type: event.content?.type })
      this.queue.push(event).catch((err) => log.error('Không lưu được sự kiện', { error: err.message }))
    }
    l.on('connected', () => { this.listenerUp = true; log.info('Listener Zalo đã nối') })
    const pushMessage = (m) => this.enrichMessage(mapMessage(m)).then(push)
      .catch((err) => log.error('Không xử lý được tin', { error: err.message }))
    l.on('message', pushMessage)
    l.on('old_messages', (msgs) => msgs.forEach(pushMessage))
    l.on('undo', (u) => push(mapUndo(u)))
    l.on('seen_messages', (list) => list.forEach((s) => push(mapSeen(s))))
    l.on('delivered_messages', (list) => list.forEach((d) => push(mapDelivered(d))))
    l.on('reaction', (r) => push(mapReaction(r)))
    l.on('error', (err) => log.warn('Listener Zalo báo lỗi', { error: String(err?.message || err) }))
    l.on('closed', (code) => this.onClosed(code))
    l.start({ retryOnClose: true })
  }

  onClosed(code) {
    this.listenerUp = false
    log.warn('Listener Zalo đóng', { code })
    if (this.state !== 'logged_in') return
    if (code === CLOSE_DUPLICATE || code === CLOSE_KICK) {
      // Có nơi khác mở Zalo Web: dừng, thử nối lại sau 10 phút.
      this.state = 'kicked'
      this.queue.push(sessionEvent('kicked')).catch(() => {})
      if (!this.kickTimer) {
        this.kickTimer = this.setTimer(() => {
          this.kickTimer = null
          if (this.state !== 'kicked' || !this.api) return
          this.state = 'logged_in'
          this.api.listener.start({ retryOnClose: true })
        }, KICK_RETRY_MS)
      }
    }
  }

  async logout() {
    if (this.qrAbort) {
      try { this.qrAbort() } catch { /* bỏ qua */ }
      this.qrAbort = null
    }
    if (this.api) {
      try { this.api.listener.stop() } catch { /* bỏ qua */ }
      try { await this.api.logout() } catch (err) { log.warn('Zalo không nhận lệnh đăng xuất', { error: err.message }) }
    }
    await this.store.clear()
    Object.assign(this, { api: null, account: null, qr: null, state: 'logged_out', listenerUp: false })
    await this.queue.push(sessionEvent('logged_out'))
  }

  requireApi() {
    if (!this.api || this.state !== 'logged_in') {
      throw new BridgeError('NOT_LOGGED_IN', 'Chưa đăng nhập Zalo hoặc phiên đang bị đá ra.', 409)
    }
    return this.api
  }

  // Tên bạn hoặc tên nhóm, đệm 6 giờ; lỗi thì null (api tự xử lý).
  async threadName(type, id, hint) {
    const key = `${type}:${id}`
    const cached = this.names.get(key)
    if (cached && this.now() - cached.at < NAME_TTL_MS) return cached.name
    let name = hint || null
    if (!name && this.api) {
      try {
        name = type === 'group'
          ? (await this.api.getGroupInfo(id)).gridInfoMap?.[id]?.name || null
          : (await this.api.getUserInfo(id)).changed_profiles?.[id]?.displayName || null
      } catch {
        name = null
      }
    }
    if (name) this.names.set(key, { name, at: this.now() })
    return name
  }

  // Thêm thread_name; với tin mình gửi qua bridge thì gắn client_ref (ghép theo msg_id).
  async enrichMessage(event) {
    const hint = event.thread_type === 'user' && !event.is_self ? event.from_name : null
    event.thread_name = await this.threadName(event.thread_type, event.thread_id, hint)
    if (event.is_self) {
      const pending = this.inflight.get(event.thread_id)
      if (pending) await Promise.race([pending.catch(() => {}), new Promise((r) => this.setTimer(r, SELF_WAIT_MS))])
      const ref = this.sentRefs.get(event.msg_id)
      if (ref) {
        event.client_ref = ref.clientRef
        this.sentRefs.delete(event.msg_id)
      }
    }
    return event
  }

  rememberSent(msgIds, clientRef) {
    const t = this.now()
    for (const [id, v] of this.sentRefs) if (t - v.at > SENT_REF_TTL_MS) this.sentRefs.delete(id)
    if (clientRef == null) return
    for (const id of msgIds) this.sentRefs.set(id, { clientRef: String(clientRef), at: t })
  }

  async conversations() {
    const api = this.requireApi()
    const friends = await api.getAllFriends()
    const items = friends.map((f) => ({
      thread_id: String(f.userId), thread_type: 'user', name: f.displayName || f.zaloName || '', avatar: f.avatar || '',
    }))
    const groupIds = Object.keys((await api.getAllGroups()).gridVerMap || {})
    for (let i = 0; i < groupIds.length; i += 50) {
      const info = await api.getGroupInfo(groupIds.slice(i, i + 50))
      for (const [id, g] of Object.entries(info.gridInfoMap || {})) {
        items.push({ thread_id: id, thread_type: 'group', name: g.name || '', avatar: g.avt || '', member_count: g.totalMember })
      }
    }
    return { items }
  }

  async groupHistory(groupId, count = 50) {
    const api = this.requireApi()
    const res = await api.getGroupChatHistory(groupId, Math.min(Math.max(count, 1), 200))
    return { items: (res.groupMsgs || []).map(mapMessage), more: Boolean(res.more) }
  }

  requestOldMessages(threadType) {
    this.requireApi().listener.requestOldMessages(threadTypeValue(threadType))
    return { requested: true }
  }

  async userInfo(uid) {
    const res = await this.requireApi().getUserInfo(uid)
    const u = res.changed_profiles?.[uid] || res.changed_profiles?.[`${uid}_0`]
    if (!u) throw new BridgeError('THREAD_NOT_FOUND', 'Không thấy người này.', 404)
    return { uid: String(uid), name: u.displayName || u.zaloName || '', avatar: u.avatar || '' }
  }

  async groupInfo(groupId) {
    const g = (await this.requireApi().getGroupInfo(groupId)).gridInfoMap?.[groupId]
    if (!g) throw new BridgeError('THREAD_NOT_FOUND', 'Không thấy nhóm này.', 404)
    return { group_id: String(groupId), name: g.name || '', avatar: g.avt || '', member_count: g.totalMember }
  }

  async download(url, hosts, label) {
    if (!hostAllowed(url, hosts)) throw new BridgeError('ATTACHMENT_HOST_NOT_ALLOWED', `Không được tải ${label} từ địa chỉ này.`)
    const res = await this.fetch(url, {
      headers: { 'user-agent': this.config.userAgent },
      signal: AbortSignal.timeout(60_000),
    })
    if (!res.ok) throw new BridgeError('DOWNLOAD_FAILED', `Không tải được ${label}.`, 502)
    const declared = Number(res.headers.get('content-length') || 0)
    if (declared > MAX_MEDIA_BYTES) throw new BridgeError('TOO_LARGE', 'Tệp quá 50 MB.', 413)
    const buf = Buffer.from(await res.arrayBuffer())
    if (buf.length > MAX_MEDIA_BYTES) throw new BridgeError('TOO_LARGE', 'Tệp quá 50 MB.', 413)
    return { buffer: buf, contentType: res.headers.get('content-type') || 'application/octet-stream' }
  }

  // Link CDN của Zalo hết hạn sau một thời gian không công bố (vài giờ); api nên tải ngay khi nhận sự kiện.
  async fetchMedia(url, name) {
    const media = await this.download(url, ZALO_MEDIA_HOSTS, 'tệp Zalo')
    let fileName = name || ''
    if (!fileName) {
      try {
        fileName = decodeURIComponent(new URL(url).pathname.split('/').pop() || '')
      } catch {
        fileName = ''
      }
    }
    return { ...media, fileName: fileName || 'zalo-media' }
  }

  async buildAttachment(file) {
    const { buffer } = await this.download(file.url, this.config.attachmentHosts, 'tệp đính kèm')
    const name = /\.[A-Za-z0-9]+$/.test(file.name || '') ? file.name : `${file.name || 'tep'}.bin`
    const metadata = { totalSize: buffer.length }
    try {
      const dim = imageSize(buffer)
      if (dim?.width && dim?.height) Object.assign(metadata, { width: dim.width, height: dim.height })
    } catch {
      /* không phải ảnh */
    }
    return { data: buffer, filename: name, metadata }
  }

  async send(body) {
    const api = this.requireApi()
    const threadId = String(body.thread_id || '')
    if (!threadId) throw new BridgeError('VALIDATION_ERROR', 'Thiếu thread_id.')
    const type = threadTypeValue(body.thread_type)
    const text = typeof body.text === 'string' ? body.text : ''
    const files = Array.isArray(body.files) ? body.files : []
    if (!text && !files.length && !body.sticker) throw new BridgeError('VALIDATION_ERROR', 'Tin trống.')
    if (text.length > 4000) throw new BridgeError('VALIDATION_ERROR', 'Tin quá 4.000 ký tự.')
    if (files.length > 5) throw new BridgeError('VALIDATION_ERROR', 'Tối đa 5 tệp mỗi tin.')

    const job = this.limiter.run(async () => {
      const ids = []
      if (body.sticker) {
        const r = await api.sendSticker(
          { id: Number(body.sticker.id), cateId: Number(body.sticker.cate_id), type: Number(body.sticker.type) || 7 },
          threadId, type,
        )
        if (r?.msgId) ids.push(String(r.msgId))
      }
      if (text || files.length) {
        const attachments = []
        for (const f of files) attachments.push(await this.buildAttachment(f))
        const r = await api.sendMessage(attachments.length ? { msg: text, attachments } : { msg: text }, threadId, type)
        if (r?.message?.msgId) ids.push(String(r.message.msgId))
        for (const a of r?.attachment || []) if (a?.msgId) ids.push(String(a.msgId))
      }
      log.info('Đã gửi tin Zalo', { thread: hashId(threadId), files: files.length, len: text.length })
      this.rememberSent(ids, body.client_ref)
      // zca-js không trả cliMsgId của tin gửi đi; api ghép bằng msg_ids và client_ref trong sự kiện is_self.
      return { msg_ids: ids, cli_msg_ids: [], client_ref: body.client_ref ?? null }
    })
    this.inflight.set(threadId, job)
    job.finally(() => { if (this.inflight.get(threadId) === job) this.inflight.delete(threadId) }).catch(() => {})
    return job
  }
}
