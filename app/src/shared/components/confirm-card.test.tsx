import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { PendingAction } from '@/shared/types/pending-action'

const getActionStatus = vi.fn<(id: number) => Promise<PendingAction>>()
vi.mock('@/shared/api/pending-action-api', () => ({
  getActionStatus: (id: number) => getActionStatus(id),
  approveAction: vi.fn(),
  rejectAction: vi.fn(),
}))
vi.mock('@/core/native/alarm', () => ({ Alarm: { sync: vi.fn() } }))

const { ConfirmCard } = await import('@/shared/components/confirm-card')

const card = {
  pending_action_id: 41,
  title: 'Gửi thư cho anh Minh',
  summary: 'Hợp đồng thuê văn phòng',
  details: [],
  confirm_label: 'Gửi',
  cancel_label: 'Bỏ',
  danger: false,
  expires_at: '2026-11-20T03:00:00Z',
}

function renderCard(action: Parameters<typeof ConfirmCard>[0]['action']) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ConfirmCard action={action} lookupStatus />
    </QueryClientProvider>,
  )
}

describe('mở lại thẻ duyệt trong lịch sử (lỗi 1.0.4)', () => {
  it('tin còn ghi pending nhưng máy chủ đã duyệt: không hiện nút, hiện giờ duyệt của máy chủ', async () => {
    getActionStatus.mockResolvedValueOnce({ id: 41, status: 'done', decided_at: '2026-11-19T03:53:21Z' } as PendingAction)
    renderCard({ ...card, status: 'pending' })
    expect(await screen.findByText(/Đã làm: Gửi thư cho anh Minh/)).toHaveTextContent('lúc 10:53')
    expect(screen.queryByRole('button', { name: 'Gửi' })).toBeNull()
  })

  it('tin đã ghi done kèm decided_at: hiện ngay, không hỏi máy chủ', () => {
    getActionStatus.mockClear()
    renderCard({ ...card, status: 'done', decided_at: '2026-11-19T03:53:21Z', result_text: 'Đã làm xong.' })
    expect(screen.getByText(/Đã làm: Gửi thư cho anh Minh/)).toHaveTextContent('lúc 10:53')
    expect(screen.queryByRole('button')).toBeNull()
    expect(getActionStatus).not.toHaveBeenCalled()
  })

  it('máy chủ xác nhận còn chờ: mới hiện nút', async () => {
    getActionStatus.mockResolvedValueOnce({ id: 41, status: 'pending' } as PendingAction)
    renderCard({ ...card })
    expect(await screen.findByRole('button', { name: 'Gửi' })).toBeInTheDocument()
  })
})
