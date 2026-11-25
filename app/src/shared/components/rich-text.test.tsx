import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { RichText } from '@/shared/components/rich-text'

describe('RichText trong Hộp tin', () => {
  const long = 'https://dashboard.render.com/web/srv-abc123/unsubscribe?token=zzzzzzzzzzzz'

  it('link dài thành chip tên miền, giữ link thật', () => {
    render(<RichText text={`Hủy nhận thư: ${long}`} compactLinks />)
    const chip = screen.getByRole('link', { name: /dashboard\.render\.com/ })
    expect(chip).toHaveAttribute('href', long)
    expect(chip).toHaveAttribute('title', long)
    expect(screen.queryByText(long)).toBeNull()
  })

  it('link ngắn giữ nguyên chữ; không gọn khi không bật', () => {
    render(<RichText text={`Xem https://x.vn/a và ${long}`} />)
    expect(screen.getByText('https://x.vn/a')).toBeInTheDocument()
    expect(screen.getByText(long)).toBeInTheDocument()
  })

  it('bấm email gọi onEmail (mở màn soạn thư)', () => {
    const onEmail = vi.fn()
    render(<RichText text="Gửi lan@example.com" onEmail={onEmail} />)
    fireEvent.click(screen.getByRole('link', { name: 'lan@example.com' }))
    expect(onEmail).toHaveBeenCalledWith('lan@example.com')
  })
})
