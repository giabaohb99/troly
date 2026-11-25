import { afterEach, describe, expect, it, vi } from 'vitest'
import { useState, type ReactElement } from 'react'
import { act, fireEvent, render as rtlRender, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Composer } from '@/modules/chat/components/composer'
import { queryKeys } from '@/shared/constants/query-keys'

// Ô nhập gọi useQuery (Công việc DEGO): bọc QueryClient, không gọi mạng.
const render = (ui: ReactElement) => rtlRender(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, enabled: false } } })}>{ui}</QueryClientProvider>)

// Giả Web Speech (bản trình duyệt của hook nhận giọng) để kiểm nút micro và tự gửi.
class FakeRecognition {
  static last: FakeRecognition | null = null
  lang = ''
  interimResults = false
  continuous = false
  onresult: ((e: unknown) => void) | null = null
  onerror: ((e: unknown) => void) | null = null
  onend: (() => void) | null = null
  start = vi.fn()
  stop = vi.fn()
  abort = vi.fn()
  constructor() {
    FakeRecognition.last = this
  }
}

describe('ô nhập: micro', () => {
  afterEach(() => {
    delete (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition
  })

  it('chưa gõ thì hiện nút micro lớn; nói xong tự gửi với cờ giọng nói', () => {
    ;(window as unknown as { webkitSpeechRecognition: unknown }).webkitSpeechRecognition = FakeRecognition
    const onSend = vi.fn()
    render(<Composer busy={false} draft="" onDraftChange={() => {}} onSend={onSend} />)
    expect(screen.queryByRole('button', { name: 'Gửi' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Nói với trợ lý' }))
    const rec = FakeRecognition.last!
    expect(rec.start).toHaveBeenCalled()
    expect(rec.lang).toBe('vi-VN')
    act(() => {
      rec.onresult?.({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: 'cơm trưa 45k' } }] })
      rec.onend?.()
    })
    expect(onSend).toHaveBeenCalledWith(expect.objectContaining({ text: 'cơm trưa 45k', voice: true }))
  })

  it('đang gõ thì là nút Gửi', () => {
    ;(window as unknown as { webkitSpeechRecognition: unknown }).webkitSpeechRecognition = FakeRecognition
    render(<Composer busy={false} draft="xin chào" onDraftChange={() => {}} onSend={() => {}} />)
    expect(screen.getByRole('button', { name: 'Gửi' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Nói với trợ lý' })).toBeNull()
  })
})

describe('ô nhập: gõ @', () => {
  function Controlled({ onSend }: { onSend: (input: unknown) => void }) {
    const [draft, setDraft] = useState('')
    return <Composer busy={false} draft={draft} onDraftChange={setDraft} onSend={onSend} sessionId={2} />
  }

  it('không còn nút chế độ; gõ @ chọn đoạn chat khác thành thẻ, gửi kèm id rồi tự bỏ thẻ', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData([...queryKeys.chat.sessionsAll, 'goi'], {
      items: [
        { id: 1, title: 'Công việc DEGO', pinned: true, last_message_at: null, last_preview: 'duyệt PO 12', created_at: null },
        { id: 2, title: 'Chi tiêu', pinned: false, last_message_at: null, last_preview: null, created_at: null },
      ],
      next_cursor: null,
    })
    const onSend = vi.fn()
    rtlRender(
      <QueryClientProvider client={client}>
        <Controlled onSend={onSend} />
      </QueryClientProvider>,
    )
    expect(screen.queryByRole('button', { name: /Tìm web|Nghĩ kỹ|Kết nối/ })).toBeNull()
    const box = screen.getByRole('textbox', { name: 'Tin nhắn' })
    fireEvent.change(box, { target: { value: '@cong', selectionStart: 5 } })
    expect(screen.queryByRole('option', { name: /Chi tiêu/ })).toBeNull()
    fireEvent.click(await screen.findByRole('option', { name: /Công việc DEGO/ }))
    expect(screen.getByRole('button', { name: 'Bỏ Công việc DEGO' })).toBeInTheDocument()
    fireEvent.change(box, { target: { value: 'tháng này việc nào trễ', selectionStart: 22 } })
    fireEvent.click(screen.getByRole('button', { name: 'Gửi' }))
    expect(onSend).toHaveBeenCalledWith(expect.objectContaining({ text: 'tháng này việc nào trễ', mode: 'chat', refs: [1] }))
    expect(screen.queryByRole('button', { name: 'Bỏ Công việc DEGO' })).toBeNull()
  })
})
