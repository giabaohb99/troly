// Máy chủ HTTP nội bộ (chỉ trong mạng compose). Mọi đường trừ /health cần Bearer ZALO_BRIDGE_TOKEN.
import { createServer } from 'node:http'
import { timingSafeEqual } from 'node:crypto'
import { log } from './log.js'
import { RateLimitError } from './send-limiter.js'
import { BridgeError } from './zalo-service.js'

const MAX_BODY = 64 * 1024

function send(res, status, body) {
  const data = JSON.stringify(body)
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'content-length': Buffer.byteLength(data) })
  res.end(data)
}

const ok = (data) => ({ success: true, message: '', data })
const fail = (code, message) => ({ success: false, message, data: { code } })

function tokenMatches(header, token) {
  const given = Buffer.from(String(header || '').replace(/^Bearer\s+/i, ''))
  const want = Buffer.from(token)
  return given.length === want.length && timingSafeEqual(given, want)
}

async function readJson(req) {
  const chunks = []
  let size = 0
  for await (const chunk of req) {
    size += chunk.length
    if (size > MAX_BODY) throw new BridgeError('TOO_LARGE', 'Thân yêu cầu quá lớn.', 413)
    chunks.push(chunk)
  }
  if (!size) return {}
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'))
  } catch {
    throw new BridgeError('VALIDATION_ERROR', 'Thân yêu cầu không phải JSON.')
  }
}

export function createApp({ service, queue, token }) {
  const routes = [
    ['GET', /^\/login\/status$/, () => service.status()],
    ['POST', /^\/login\/qr$/, () => service.startQR()],
    ['POST', /^\/logout$/, async () => { await service.logout(); return service.status() }],
    ['GET', /^\/conversations$/, () => service.conversations()],
    ['GET', /^\/conversations\/([^/]+)\/messages$/, (m, url) => {
      if (url.searchParams.get('thread_type') !== 'group') {
        throw new BridgeError('NOT_SUPPORTED', 'Zalo chỉ trả lịch sử cho nhóm; tin một-một lấy từ sự kiện.', 400)
      }
      return service.groupHistory(decodeURIComponent(m[1]), Number(url.searchParams.get('count') || 50))
    }],
    ['POST', /^\/sync\/old-messages$/, async (m, url, body) => service.requestOldMessages(body.thread_type)],
    ['POST', /^\/messages$/, async (m, url, body) => service.send(body)],
    ['GET', /^\/users\/([^/]+)$/, (m) => service.userInfo(decodeURIComponent(m[1]))],
    ['GET', /^\/groups\/([^/]+)$/, (m) => service.groupInfo(decodeURIComponent(m[1]))],
  ]

  return createServer(async (req, res) => {
    const url = new URL(req.url, 'http://bridge')
    try {
      if (req.method === 'GET' && url.pathname === '/health') {
        return send(res, 200, ok({ status: 'ok', login_state: service.state, listener: service.listenerUp, queue_size: queue.size }))
      }
      if (!tokenMatches(req.headers.authorization, token)) {
        return send(res, 401, fail('UNAUTHORIZED', 'Sai khóa nội bộ.'))
      }
      if (req.method === 'POST' && url.pathname === '/media/fetch') {
        const body = await readJson(req)
        const media = await service.fetchMedia(String(body.url || ''), body.name ? String(body.name) : '')
        res.writeHead(200, {
          'content-type': media.contentType,
          'content-length': media.buffer.length,
          'x-file-name': encodeURIComponent(media.fileName),
          'content-disposition': `attachment; filename*=UTF-8''${encodeURIComponent(media.fileName)}`,
        })
        return res.end(media.buffer)
      }
      for (const [method, pattern, handler] of routes) {
        const m = url.pathname.match(pattern)
        if (!m || req.method !== method) continue
        const body = method === 'POST' ? await readJson(req) : {}
        return send(res, 200, ok(await handler(m, url, body)))
      }
      return send(res, 404, fail('NOT_FOUND', 'Không có đường này.'))
    } catch (err) {
      if (err instanceof RateLimitError) {
        res.setHeader('retry-after', String(err.retryAfter))
        return send(res, 429, { success: false, message: err.message, data: { code: err.code, retry_after: err.retryAfter } })
      }
      if (err instanceof BridgeError) return send(res, err.status, fail(err.code, err.message))
      log.error('Lỗi xử lý yêu cầu', { path: url.pathname, error: err?.message })
      return send(res, 502, fail('ZALO_ERROR', 'Zalo không phản hồi đúng, thử lại sau.'))
    }
  })
}
