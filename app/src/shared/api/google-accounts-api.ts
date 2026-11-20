import { useQuery } from '@tanstack/react-query'
import { apiDelete, apiGet, apiPost } from '@/core/api/http-client'
import { queryKeys } from '@/shared/constants/query-keys'

// Nhiều tài khoản Gmail (QĐ-50): tài khoản chính giữ Lịch, Việc, Drive và Gmail; tài khoản thêm chỉ Gmail (đọc, soạn,
// gửi qua thẻ duyệt). Dạng đã chốt với agent Google (20/11).

export interface GoogleAccount {
  id: number
  email: string
  role: 'primary' | 'mail'
  status: 'active' | 'reauth_required' | 'revoked'
  last_sync_at: string | null
  last_error: string | null
  // Gói đang bật: tài khoản chính có calendar, tasks, gmail...; tài khoản thêm chỉ gmail.
  enabled_packs?: string[]
}

// Loại thư Gmail vào Hộp tin; thư IMPORTANT luôn vào.
// Khóa cài đặt `gmail.categories`.
export type InboxCategories = 'primary' | 'primary_updates' | 'all'

export const INBOX_CATEGORY_OPTIONS: { value: InboxCategories; label: string; text: string }[] = [
  { value: 'primary', label: 'Chính', text: 'Chỉ thư ở mục Chính.' },
  { value: 'primary_updates', label: 'Chính và Cập nhật', text: 'Thêm thư Cập nhật: xác nhận đặt chỗ, hóa đơn, thông báo tài khoản. Mặc định.' },
  { value: 'all', label: 'Tất cả trừ Quảng cáo, Mạng xã hội', text: 'Cả hộp thư đến, thêm mục Diễn đàn.' },
]

export const listGoogleAccounts = () => apiGet<{ items: GoogleAccount[] }>('/google/accounts')
export const connectMailAccount = () => apiPost<{ auth_url: string }>('/google/connect', { role: 'mail' })
// deleteMessages: bỏ thư của tài khoản khỏi Hộp tin (mặc định của máy chủ là có).
export const removeGoogleAccount = (id: number, deleteMessages = true) => apiDelete<{ ok: boolean }>(`/google/accounts/${id}?delete_messages=${deleteMessages}`)

export function useGoogleAccounts(enabled = true) {
  return useQuery({ queryKey: queryKeys.google.accounts, queryFn: listGoogleAccounts, enabled, staleTime: 60_000, select: (d) => sortAccounts(d.items) })
}

// Chính đứng đầu, rồi các tài khoản thêm theo thứ tự máy chủ trả.
export function sortAccounts(items: GoogleAccount[]): GoogleAccount[] {
  return [...items.filter((a) => a.role === 'primary'), ...items.filter((a) => a.role !== 'primary')]
}

export function accountRoleText(account: GoogleAccount): string {
  return account.role === 'primary' ? 'Chính: Lịch, Việc, Gmail' : 'Thêm: chỉ Gmail'
}

// Tài khoản gửi mặc định: tài khoản nhận thư đang trả lời (nếu còn), không thì tài khoản chính.
export function defaultSenderId(accounts: GoogleAccount[], replyFromEmail?: string | null): number | null {
  const usable = accounts.filter((a) => a.status !== 'revoked')
  const match = replyFromEmail ? usable.find((a) => a.email.toLowerCase() === replyFromEmail.toLowerCase()) : undefined
  return (match ?? usable.find((a) => a.role === 'primary') ?? usable[0])?.id ?? null
}
