import { describe, expect, it } from 'vitest'
import { anyConnected, connectErrorText, connectorStatusText, nameFromUrl, toggledWriteTools, validConnectorUrl, type Connector } from '@/shared/api/connectors-api'

const c = (extra: Partial<Connector>): Connector => ({ id: 1, name: 'ERP DEGO', url: 'https://erp.degoholding.vn/mcp', auth: 'oauth', status: 'not_connected', account: null, last_error: null, write_enabled: false, tools_count: null, created_at: '2026-11-25T00:00:00Z', ...extra })

describe('Kết nối (QĐ-56)', () => {
  it('dòng trạng thái', () => {
    expect(connectorStatusText(c({}))).toBe('Chưa nối')
    expect(connectorStatusText(c({ auth: 'api_key' }))).toBe('Chưa có khóa')
    expect(connectorStatusText(c({ status: 'connected', account: 'bao@dego.vn' }))).toBe('Đã nối tài khoản bao@dego.vn')
    expect(connectorStatusText(c({ status: 'reauth_required' }))).toBe('Cần nối lại')
    expect(connectorStatusText(c({ status: 'error', last_error: 'Hết hạn' }))).toBe('Hết hạn')
  })

  it('nút Kết nối trong chat chỉ hiện khi đã nối ít nhất một hệ thống', () => {
    expect(anyConnected(undefined)).toBe(false)
    expect(anyConnected([c({}), c({ id: 2, status: 'reauth_required' })])).toBe(false)
    expect(anyConnected([c({ status: 'connected' })])).toBe(true)
  })

  it('địa chỉ MCP: https, localhost được http', () => {
    expect(validConnectorUrl('https://erp.degoholding.vn/mcp')).toBeNull()
    expect(validConnectorUrl('http://localhost:3000/mcp')).toBeNull()
    expect(validConnectorUrl('http://erp.vn/mcp')).toBe('Địa chỉ phải bắt đầu bằng https://')
    expect(validConnectorUrl('erp')).toBe('Địa chỉ chưa đúng.')
    expect(validConnectorUrl(' ')).toBe('Nhập địa chỉ MCP.')
    expect(nameFromUrl('https://www.erp.degoholding.vn/mcp')).toBe('erp.degoholding.vn')
  })

  it('mã lỗi khi về từ trang đăng nhập, danh sách công cụ ghi bật', () => {
    expect(connectErrorText('huy')).toBe('Đã hủy kết nối.')
    expect(connectErrorText('token')).toBe('Không đổi được mã đăng nhập.')
    expect(connectErrorText('la')).toBe('Chưa nối được, thử lại sau.')
    expect(connectErrorText(null)).toBe('Chưa nối được, thử lại sau.')
    expect(toggledWriteTools(['update_leave'], 'create_task', true)).toEqual(['create_task', 'update_leave'])
    expect(toggledWriteTools(['create_task', 'update_leave'], 'create_task', false)).toEqual(['update_leave'])
    expect(toggledWriteTools(undefined, 'create_task', false)).toEqual([])
  })
})
