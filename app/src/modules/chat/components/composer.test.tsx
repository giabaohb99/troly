import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ReactElement } from 'react'
import { act, fireEvent, render as rtlRender, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Composer } from '@/modules/chat/components/composer'

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
