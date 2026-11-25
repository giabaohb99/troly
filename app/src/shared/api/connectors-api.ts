import { useQuery } from '@tanstack/react-query'
import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from '@/core/api/http-client'

// Kết nối (QĐ-56, thay màn DEGO của QĐ-55): danh sách máy chủ MCP như Claude. Thêm bằng tên và địa chỉ; máy chủ có
// OAuth thì đăng nhập trên trang của hệ thống (trình duyệt trong app), không có thì dán khóa. Công cụ ghi mặc định
// tắt, bật từng công cụ theo tên. Dạng đã chốt với agent Google (25/11), sau cờ connectors.

export interface Connector {
  id: number
  name: string
  url: string
  auth: 'oauth' | 'api_key' | 'none'
  status: 'connected' | 'not_connected' | 'reauth_required' | 'error'
  account: string | null
  last_error: string | null
  // Tên các công cụ ghi đang bật; write_enabled chỉ để đọc (true khi có ít nhất một công cụ ghi bật).
  write_tools_enabled?: string[]
  write_enabled: boolean
  tools_count: number | null
  access_expires_at?: string | null
  connected_at?: string | null
  created_at: string
}

export interface ConnectorTool {
  name: string
  title?: string | null
  description: string | null
  write: boolean
  // Công cụ đọc luôn bật; công cụ ghi bật theo write_tools_enabled.
  enabled: boolean
}

export interface ConnectorPreset {
  name: string
  url: string
}

// Gợi ý khi máy chủ chưa trả danh sách gợi ý.
export const FALLBACK_PRESETS: ConnectorPreset[] = [{ name: 'ERP DEGO', url: 'https://erp.degoholding.vn/api/mcp' }]

export const CONNECTORS_KEY = ['connectors'] as const

export const listConnectors = () => apiGet<{ items: Connector[] }>('/connectors')
export const listPresets = () => apiGet<{ items: ConnectorPreset[] }>('/connectors/presets').then((r) => r.items)
export const addConnector = (input: { name: string; url: string }) => apiPost<{ connector: Connector; next: 'oauth' | 'api_key' | 'ready' }>('/connectors', input)
export const startConnect = (id: number) => apiPost<{ auth_url: string }>(`/connectors/${id}/connect`)
export const saveConnectorKey = (id: number, apiKey: string) => apiPut<Connector>(`/connectors/${id}/key`, { api_key: apiKey })
export const listConnectorTools = (id: number) => apiGet<{ items: ConnectorTool[] }>(`/connectors/${id}/tools`)
// Bật công cụ ghi theo tên: gửi lại cả danh sách công cụ ghi đang bật.
export const updateConnector = (id: number, patch: { name?: string; write_tools_enabled?: string[] }) => apiPatch<Connector>(`/connectors/${id}`, patch)
export const removeConnector = (id: number) => apiDelete<unknown>(`/connectors/${id}`)

export function useConnectors(enabled = true) {
  return useQuery({ queryKey: CONNECTORS_KEY, queryFn: listConnectors, enabled, staleTime: 5 * 60_000, select: (d) => d.items, retry: 1 })
}

export function connectorStatusText(c: Connector): string {
  if (c.status === 'connected') return c.account ? `Đã nối tài khoản ${c.account}` : 'Đã nối'
  if (c.status === 'reauth_required') return 'Cần nối lại'
  if (c.status === 'error') return c.last_error || 'Lỗi kết nối'
  return c.auth === 'api_key' ? 'Chưa có khóa' : 'Chưa nối'
}

// Nút Kết nối trong chat chỉ hiện khi đã nối ít nhất một máy chủ.
export function anyConnected(items: Connector[] | undefined): boolean {
  return !!items?.some((c) => c.status === 'connected')
}

// Địa chỉ MCP hợp lệ: https (cho phép http với localhost để thử).
export function validConnectorUrl(url: string): string | null {
  const u = url.trim()
  if (!u) return 'Nhập địa chỉ MCP.'
  try {
    const parsed = new URL(u)
    if (parsed.protocol === 'https:' || (parsed.protocol === 'http:' && /^(localhost|127\.0\.0\.1)$/.test(parsed.hostname))) return null
    return 'Địa chỉ phải bắt đầu bằng https://'
  } catch {
    return 'Địa chỉ chưa đúng.'
  }
}

// Đặt tên gợi ý theo địa chỉ khi người dùng để trống tên: erp.degoholding.vn thành erp.degoholding.vn.
export function nameFromUrl(url: string): string {
  try {
    return new URL(url.trim()).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

// Mã lỗi khi về từ trang đăng nhập (troly://settings/connectors?ok=0&loi=<mã>): app tự hiện câu.
const CONNECT_ERRORS: Record<string, string> = {
  huy: 'Đã hủy kết nối.',
  state: 'Phiên kết nối hết hạn, thử lại.',
  iss: 'Phản hồi không đúng máy chủ.',
  token: 'Không đổi được mã đăng nhập.',
  loi: 'Máy chủ báo lỗi.',
}

export function connectErrorText(code: string | null): string {
  return (code && CONNECT_ERRORS[code]) || 'Chưa nối được, thử lại sau.'
}

// Danh sách công cụ ghi bật sau khi đổi một công tắc.
export function toggledWriteTools(current: string[] | undefined, name: string, on: boolean): string[] {
  const set = new Set(current ?? [])
  if (on) set.add(name)
  else set.delete(name)
  return [...set].sort()
}

