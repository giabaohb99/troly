import { ApiError, NETWORK_ERROR_MESSAGE } from '@/core/api/api-error'
import { buildHeaders, ensureAccessToken, toApiError } from '@/core/api/http-client'
import { apiBase } from '@/core/config'

// Đọc luồng Server-Sent Events từ fetch (EventSource không gửi được POST và tiêu đề Authorization).

export interface SseEvent {
  event: string
  data: string
}

// Bộ tách sự kiện: nhận từng mảnh chữ, gọi onEvent mỗi khi đủ một sự kiện (kết thúc bằng dòng trống).
// Bỏ dòng chú thích (`: ping`). Hỗ trợ cả \r\n.
export function createSseParser(onEvent: (event: SseEvent) => void) {
  let buffer = ''
  let eventName = 'message'
  let dataLines: string[] = []

  const dispatch = () => {
    if (dataLines.length > 0) onEvent({ event: eventName, data: dataLines.join('\n') })
    eventName = 'message'
    dataLines = []
  }

  const handleLine = (line: string) => {
    if (line === '') return dispatch()
    if (line.startsWith(':')) return
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') eventName = value
    else if (field === 'data') dataLines.push(value)
  }

  return {
    push(chunk: string) {
      buffer += chunk
      let index: number
      while ((index = buffer.search(/\r?\n/)) !== -1) {
        const line = buffer.slice(0, index)
        buffer = buffer.slice(index + (buffer[index] === '\r' ? 2 : 1))
        handleLine(line)
      }
    },
    end() {
      if (buffer) handleLine(buffer)
      buffer = ''
      dispatch()
    },
  }
}

// POST và đọc luồng SSE. Lỗi trước khi bắt đầu luồng (máy chủ trả phong bì JSON) ném ApiError.
export async function postEventStream(path: string, body: unknown, onEvent: (event: SseEvent) => void, signal?: AbortSignal): Promise<void> {
  const send = async (token: string | null) => {
    try {
      return await fetch(`${apiBase}${path}`, {
        method: 'POST',
        signal,
        headers: buildHeaders(token, { Accept: 'text/event-stream', 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new ApiError(0, NETWORK_ERROR_MESSAGE, 'NETWORK')
    }
  }

  let res = await send(await ensureAccessToken())
  if (res.status === 401) {
    const token = await ensureAccessToken(true)
    if (token) res = await send(token)
  }
  if (!res.ok) throw await toApiError(res, path)
  if (!res.headers.get('Content-Type')?.includes('text/event-stream') || !res.body) {
    throw new ApiError(res.status, 'Máy chủ không trả luồng trả lời.', 'BAD_RESPONSE')
  }

  const parser = createSseParser(onEvent)
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      parser.push(value)
    }
    parser.end()
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'Mất kết nối giữa chừng.', 'STREAM_INTERRUPTED')
  }
}
