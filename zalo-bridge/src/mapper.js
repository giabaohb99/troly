// Đổi đối tượng của zca-js sang sự kiện theo hợp đồng ở docs/50-ha-tang mục 3.15.
// ThreadType của zca-js: User = 0, Group = 1.

export const threadTypeName = (type) => (type === 1 ? 'group' : 'user')
export const threadTypeValue = (name) => (name === 'group' ? 1 : 0)

function isoFromMs(ms) {
  const n = Number(ms)
  return Number.isFinite(n) && n > 0 ? new Date(n).toISOString() : new Date().toISOString()
}

function parseParams(params) {
  if (!params || typeof params !== 'string') return {}
  try {
    return JSON.parse(params)
  } catch {
    return {}
  }
}

export function mapContent(msgType, content) {
  if (typeof content === 'string') return { type: 'text', text: content }
  const c = content || {}
  const params = parseParams(c.params)
  switch (msgType) {
    case 'chat.photo':
      return { type: 'image', text: c.title || '', media: { url: c.href || '', thumb: c.thumb || '' } }
    case 'chat.video.msg':
      return { type: 'video', text: c.title || '', media: { url: c.href || '', thumb: c.thumb || '' } }
    case 'chat.voice':
      return { type: 'voice', media: { url: c.href || '' } }
    case 'chat.sticker':
      return { type: 'sticker', sticker: { id: Number(c.id) || 0, cate_id: Number(c.catId ?? c.cateId) || 0 } }
    case 'share.file':
      return {
        type: 'file',
        media: { url: c.href || '', name: c.title || '', size: Number(params.fileSize) || 0 },
      }
    case 'chat.recommended':
    case 'chat.link':
      return { type: 'link', text: c.description || '', link: { url: c.href || '', title: c.title || '' } }
    case 'chat.location.new':
      return { type: 'location', text: c.title || c.description || '' }
    default:
      return { type: 'other', text: c.title || c.description || '' }
  }
}

export function mapMessage(message) {
  const d = message.data
  const event = {
    event_id: `msg:${d.msgId}`,
    kind: 'message',
    ts: isoFromMs(d.ts),
    thread_id: String(message.threadId),
    thread_type: threadTypeName(message.type),
    msg_id: String(d.msgId),
    cli_msg_id: String(d.cliMsgId ?? ''),
    from_uid: String(d.uidFrom ?? ''),
    from_name: d.dName || '',
    is_self: Boolean(message.isSelf),
    content: mapContent(d.msgType, d.content),
  }
  if (d.quote) {
    event.quote = { msg_id: String(d.quote.globalMsgId ?? ''), text: d.quote.msg || '' }
  }
  if (Array.isArray(d.mentions) && d.mentions.length) {
    event.mentions = d.mentions.map((m) => ({ uid: String(m.uid), pos: m.pos, len: m.len }))
  }
  return event
}

export function mapUndo(undo) {
  const d = undo.data
  return {
    event_id: `undo:${d.msgId}`,
    kind: 'undo',
    ts: isoFromMs(d.ts),
    thread_id: String(undo.threadId),
    thread_type: undo.isGroup ? 'group' : 'user',
    msg_id: String(d.msgId),
    undo_msg_id: String(d.content?.globalMsgId ?? ''),
    from_uid: String(d.uidFrom ?? ''),
    is_self: Boolean(undo.isSelf),
  }
}

export function mapSeen(seen) {
  const d = seen.data
  const uids = d.seenUids ? d.seenUids.map(String) : []
  return {
    event_id: `seen:${seen.threadId}:${d.msgId}:${uids.join(',')}`,
    kind: 'seen',
    ts: new Date().toISOString(),
    thread_id: String(seen.threadId),
    thread_type: threadTypeName(seen.type),
    msg_ids: [String(d.msgId)],
    seen_uids: uids,
  }
}

export function mapDelivered(delivered) {
  const d = delivered.data
  return {
    event_id: `delivered:${delivered.threadId}:${d.msgId}`,
    kind: 'delivered',
    ts: isoFromMs(d.mSTs),
    thread_id: String(delivered.threadId),
    thread_type: threadTypeName(delivered.type),
    msg_ids: [String(d.msgId)],
  }
}

export function mapReaction(reaction) {
  const d = reaction.data
  const target = d.content?.rMsg?.[0]
  return {
    event_id: `reaction:${d.msgId}`,
    kind: 'reaction',
    ts: isoFromMs(d.ts),
    thread_id: String(reaction.threadId),
    thread_type: reaction.isGroup ? 'group' : 'user',
    msg_id: String(target?.gMsgID ?? ''),
    from_uid: String(d.uidFrom ?? ''),
    is_self: Boolean(reaction.isSelf),
    icon: d.content?.rIcon ?? '',
  }
}

export function sessionEvent(state, extra = {}) {
  const ts = new Date().toISOString()
  return {
    event_id: `session:${state}:${ts}`,
    kind: 'session',
    ts,
    state,
    ...extra,
  }
}
