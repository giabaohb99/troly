import { useQuery } from '@tanstack/react-query'
import { apiGet, apiPost } from '@/core/api/http-client'

// Đăng nhập Zalo qua zalo-bridge (QĐ-52, 50 mục 3.15, route của agent kiến trúc). Chỉ dùng khi cờ zalo_bridge bật.

export type ZaloState = 'logged_out' | 'waiting_scan' | 'scanned' | 'logged_in' | 'expired' | 'kicked' | 'error' | 'unavailable'

export interface ZaloStatus {
  state: ZaloState
  account: { uid: string; name: string } | null
  qr_png_base64?: string | null
  qr_expires_at?: string | null
  last_event_at?: string | null
  message?: string | null
}

export const ZALO_STATUS_KEY = ['zalo', 'status'] as const

export const getZaloStatus = () => apiGet<ZaloStatus>('/zalo/status')
export const startZaloLogin = () => apiPost<ZaloStatus>('/zalo/login')
export const zaloLogout = () => apiPost<ZaloStatus>('/zalo/logout')

// Đang chờ quét hoặc vừa quét: hỏi lại mỗi 2 giây (hợp đồng zalo-bridge).
export const isZaloWaiting = (state: ZaloState | undefined) => state === 'waiting_scan' || state === 'scanned'

export function useZaloStatus(enabled = true) {
  return useQuery({
    queryKey: ZALO_STATUS_KEY,
    queryFn: getZaloStatus,
    enabled,
    retry: 1,
    refetchInterval: (q) => (isZaloWaiting(q.state.data?.state) ? 2_000 : false),
  })
}

// Câu trạng thái cho màn Cài đặt → Zalo.
export function zaloStateText(s: Pick<ZaloStatus, 'state' | 'account' | 'message'>): string {
  switch (s.state) {
    case 'logged_in':
      return s.account ? `Đã đăng nhập ${s.account.name}` : 'Đã đăng nhập'
    case 'waiting_scan':
      return 'Mở Zalo trên điện thoại khác hoặc máy tính, quét mã này'
    case 'scanned':
      return 'Đã quét, bấm Đồng ý trong Zalo'
    case 'expired':
      return 'Mã QR hết hạn, tạo mã mới'
    case 'kicked':
      return 'Zalo Web vừa mở ở nơi khác nên trợ lý bị đăng xuất; tự thử lại sau 10 phút'
    case 'unavailable':
      return s.message || 'Dịch vụ Zalo đang tắt'
    case 'error':
      return s.message || 'Zalo báo lỗi, thử đăng nhập lại'
    default:
      return 'Chưa đăng nhập'
  }
}
