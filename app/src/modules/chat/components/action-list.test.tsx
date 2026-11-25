import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { ActionList } from '@/modules/chat/components/action-list'
import { FEATURES_KEY } from '@/shared/hooks/use-features'

function Where() {
  const location = useLocation()
  return <p data-testid="where">{`${location.pathname} ${JSON.stringify(location.state)}`}</p>
}

describe('nút Kết nối trợ lý gửi (QĐ-56)', () => {
  it('chưa có kết nối thì mở form thêm điền sẵn tên, địa chỉ', () => {
    // Cờ connectors bật (như /system/status trả); thiếu cờ thì nút không hiện.
    const client = new QueryClient()
    client.setQueryData(FEATURES_KEY, { features: { connectors: true } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route path="/" element={<ActionList actions={[{ id: 'k1', type: 'connect', label: 'Kết nối ERP DEGO', name: 'ERP DEGO', url: 'https://erp.degoholding.vn/mcp' }]} />} />
            <Route path="/cai-dat/ket-noi" element={<Where />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: /Kết nối ERP DEGO/ }))
    expect(screen.getByTestId('where').textContent).toBe('/cai-dat/ket-noi {"add":{"name":"ERP DEGO","url":"https://erp.degoholding.vn/mcp"}}')
  })
})
