import { describe, expect, it } from 'vitest'
import { applyTurnEvent, finishTurnWithoutCompletion, startTurn, type ChatTurn } from '@/modules/chat/utils/turn-reducer'

const ev = (event: string, data: unknown) => ({ event, data: JSON.stringify(data) })

function run(events: { event: string; data: string }[]): ChatTurn {
  return events.reduce(applyTurnEvent, startTurn('id-1', 'cơm trưa 45k'))
}

describe('applyTurnEvent', () => {
  it('nối chữ, hiện nhãn công cụ, gom hành động', () => {
    const turn = run([
      ev('message.created', { user_message: { id: 1, role: 'user', text: 'cơm trưa 45k' }, conversation_id: 9 }),
      ev('tool.started', { name: 'add_expense', label: 'Đang ghi khoản chi' }),
      ev('tool.finished', { name: 'add_expense', ok: true }),
      ev('text.delta', { text: 'Ghi 45.000 đ ' }),
      ev('text.delta', { text: 'ăn uống.' }),
      ev('action', { id: 'a1', type: 'open_screen', label: 'Sửa khoản này', screen: 'expense_detail', params: { expense_id: 5 } }),
    ])
    expect(turn.text).toBe('Ghi 45.000 đ ăn uống.')
    expect(turn.conversationId).toBe(9)
    expect(turn.toolLabel).toBeNull()
    expect(turn.actions).toHaveLength(1)
    expect(turn.status).toBe('streaming')
  })

  it('nhãn công cụ hiện khi đang chạy', () => {
    const turn = run([ev('tool.started', { name: 'web_search', label: 'Đang tìm trên web' })])
    expect(turn.toolLabel).toBe('Đang tìm trên web')
  })

  it('bỏ hành động kiểu lạ', () => {
    const turn = run([ev('action', { id: 'a9', type: 'teleport', label: 'x' })])
    expect(turn.actions).toHaveLength(0)
  })

  it('message.completed thay chữ bằng chữ cuối, giữ model và nguồn', () => {
    const turn = run([
      ev('text.delta', { text: 'Giá vàng...' }),
      ev('message.completed', { assistant_message: { id: 884, model: 'claude-sonnet-5-5', text: 'Giá vàng SJC 94,1 tr.', citations: [{ title: 'SJC', url: 'https://sjc.com.vn' }] } }),
    ])
    expect(turn.status).toBe('done')
    expect(turn.assistant?.id).toBe(884)
    expect(turn.assistant?.text).toBe('Giá vàng SJC 94,1 tr.')
    expect(turn.assistant?.model).toBe('claude-sonnet-5-5')
    expect(turn.assistant?.citations).toHaveLength(1)
  })

  it('message.completed không có chữ thì giữ chữ đã chạy và hành động', () => {
    const turn = run([
      ev('text.delta', { text: 'Ghi xong.' }),
      ev('action', { id: 'a1', type: 'undo', label: 'Hoàn tác', text: 'Đã ghi', resource: 'expense', ids: [5], expires_at: '2026-11-18T12:10:00+07:00' }),
      ev('message.completed', { assistant_message: { id: 2, model: 'claude-haiku-5-5' } }),
    ])
    expect(turn.assistant?.text).toBe('Ghi xong.')
    expect(turn.assistant?.actions).toHaveLength(1)
  })

  it('sự kiện error kết thúc lượt', () => {
    const turn = run([ev('error', { code: 'AI_UNAVAILABLE', message: 'Trợ lý đang lỗi.' })])
    expect(turn.status).toBe('error')
    expect(turn.error?.code).toBe('AI_UNAVAILABLE')
  })

  it('dữ liệu hỏng thì bỏ qua', () => {
    const turn = applyTurnEvent(startTurn('x', 'y'), { event: 'text.delta', data: 'not json' })
    expect(turn.text).toBe('')
  })

  it('luồng đóng giữa chừng thành lỗi mất kết nối', () => {
    const turn = finishTurnWithoutCompletion(run([ev('text.delta', { text: 'a' })]))
    expect(turn.error?.code).toBe('STREAM_INTERRUPTED')
  })
})
