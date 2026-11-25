// zca-js giả cho bài kiểm: điều khiển đăng nhập QR và phát sự kiện listener bằng tay.
import { EventEmitter } from 'node:events'

export class FakeListener extends EventEmitter {
  constructor() {
    super()
    this.started = 0
    this.stopped = 0
    this.oldRequests = []
  }
  start() { this.started += 1; this.emit('connected') }
  stop() { this.stopped += 1 }
  requestOldMessages(type) { this.oldRequests.push(type) }
}

export class FakeApi {
  constructor() {
    this.listener = new FakeListener()
    this.sent = []
    this.stickers = []
    this.loggedOut = false
  }
  getOwnId() { return '900100' }
  async fetchAccountInfo() { return { profile: { displayName: 'Chủ tài khoản' } } }
  async sendMessage(content, threadId, type) {
    this.sent.push({ content, threadId, type })
    return { message: { msgId: 111 }, attachment: (content.attachments || []).map((_, i) => ({ msgId: 200 + i })) }
  }
  async sendSticker(sticker, threadId, type) { this.stickers.push({ sticker, threadId, type }); return { msgId: 333 } }
  async getAllFriends() { return [{ userId: '1', displayName: 'Lan', avatar: 'a1' }] }
  async getAllGroups() { return { gridVerMap: { g1: '1' } } }
  async getGroupInfo(ids) {
    const list = Array.isArray(ids) ? ids : [ids]
    return { gridInfoMap: Object.fromEntries(list.map((id) => [id, { name: 'Nhóm ' + id, avt: 'g', totalMember: 3 }])) }
  }
  async getGroupChatHistory() { return { groupMsgs: [], more: 0 } }
  async getUserInfo(uid) { return { changed_profiles: { [uid]: { displayName: 'Lan', avatar: 'a1' } } } }
  async logout() { this.loggedOut = true; return {} }
}

// Tạo lớp Zalo giả; `control` cho bài kiểm phát sự kiện QR và kết thúc đăng nhập.
export function makeFakeZalo() {
  const control = { api: new FakeApi(), qrCallback: null, resolveQR: null, rejectQR: null, logins: [] }
  class FakeZalo {
    constructor(options) { this.options = options }
    async login(creds) { control.logins.push(creds); return control.api }
    loginQR(options, callback) {
      control.qrCallback = callback
      return new Promise((resolve, reject) => {
        control.resolveQR = resolve
        control.rejectQR = reject
        queueMicrotask(() => callback({
          type: 0, data: { image: 'UVJQTkc=', code: 'c', token: 't' }, actions: { abort: () => reject(new Error('aborted')) },
        }))
      })
    }
  }
  control.scan = () => control.qrCallback({ type: 2, data: { display_name: 'Chủ tài khoản', avatar: '' } })
  control.finish = (creds = { cookie: [{ key: 'zpw', value: 'bi-mat' }], imei: 'imei-1', userAgent: 'UA' }) => {
    control.qrCallback({ type: 4, data: { cookie: creds.cookie, imei: creds.imei, userAgent: creds.userAgent } })
    control.resolveQR(control.api)
  }
  return { FakeZalo, control }
}
