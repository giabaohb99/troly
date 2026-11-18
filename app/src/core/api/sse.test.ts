import { describe, expect, it } from 'vitest'
import { createSseParser, type SseEvent } from '@/core/api/sse'

function collect(chunks: string[]): SseEvent[] {
  const events: SseEvent[] = []
  const parser = createSseParser((event) => events.push(event))
  for (const chunk of chunks) parser.push(chunk)
  parser.end()
  return events
}

describe('createSseParser', () => {
  it('tách sự kiện có tên', () => {
    const events = collect(['event: text.delta\ndata: {"text":"Chào"}\n\n'])
    expect(events).toEqual([{ event: 'text.delta', data: '{"text":"Chào"}' }])
  })

  it('ghép sự kiện bị cắt giữa các mảnh, cả \\r\\n', () => {
    const events = collect(['event: tool.sta', 'rted\r\ndata: {"name":"a"', '}\r\n\r\nevent: text.delta\n', 'data: {"text":"x"}\n\n'])
    expect(events.map((e) => e.event)).toEqual(['tool.started', 'text.delta'])
    expect(events[0].data).toBe('{"name":"a"}')
  })

  it('bỏ dòng ping và nối nhiều dòng data', () => {
    const events = collect([': ping\n\n', 'data: a\ndata: b\n\n'])
    expect(events).toEqual([{ event: 'message', data: 'a\nb' }])
  })

  it('phát sự kiện cuối dù luồng đóng không có dòng trống', () => {
    const events = collect(['event: message.completed\ndata: {}'])
    expect(events).toEqual([{ event: 'message.completed', data: '{}' }])
  })
})
