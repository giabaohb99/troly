import type { Conversation } from '@/modules/inbox/types/inbox'

// Danh sách Hộp tin (phản hồi 1.0.7): luôn xếp theo tin mới nhất giảm dần; quan trọng chỉ là ngôi sao, không đẩy lên
// đầu (tab Quan trọng vẫn lọc riêng). Tab Email lọc được theo tài khoản nhận.

export function sortByLatest(items: Conversation[]): Conversation[] {
  return [...items].sort((a, b) => Date.parse(b.last_posted_at) - Date.parse(a.last_posted_at))
}

const same = (a: string | null | undefined, b: string | null | undefined) => !!a && !!b && a.toLowerCase() === b.toLowerCase()

export function filterByAccount(items: Conversation[], account: string | null): Conversation[] {
  if (!account) return items
  return items.filter((c) => c.app !== 'gmail' || same(c.account_email, account))
}

// Tên ngắn của tài khoản: phần trước @ (hgbao.idagroup@gmail.com thành hgbao.idagroup).
export function accountShort(email: string): string {
  return email.split('@')[0] || email
}

// Danh sách tài khoản cho hàng chip: theo thứ tự tài khoản đã nối (chính trước), thêm tài khoản chỉ thấy trong thư.
export function accountChoices(connected: string[], items: Conversation[]): string[] {
  const out: string[] = []
  const add = (email: string | null | undefined) => {
    if (email && !out.some((e) => same(e, email))) out.push(email)
  }
  connected.forEach(add)
  items.forEach((c) => c.app === 'gmail' && add(c.account_email))
  return out
}

// Màu huy hiệu theo vị trí tài khoản (tài khoản chính màu đầu); token màu, không hex lẻ.
export const ACCOUNT_COLORS = ['bg-app-3/20 text-app-3', 'bg-app-4/20 text-app-4', 'bg-app-6/20 text-app-6', 'bg-app-1/20 text-app-1', 'bg-app-2/20 text-app-2'] as const

export function accountColor(email: string, accounts: string[]): string {
  const index = accounts.findIndex((a) => same(a, email))
  if (index >= 0) return ACCOUNT_COLORS[index % ACCOUNT_COLORS.length]
  let hash = 0
  for (const ch of email.toLowerCase()) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return ACCOUNT_COLORS[hash % ACCOUNT_COLORS.length]
}

// Nhớ lựa chọn tài khoản cuối ở tab Email (lưu trên máy).
const KEY = 'troly.inbox.gmail_account'

export function getSavedAccount(): string | null {
  try {
    return localStorage.getItem(KEY) || null
  } catch {
    return null
  }
}

export function saveAccount(email: string | null) {
  try {
    if (email) localStorage.setItem(KEY, email)
    else localStorage.removeItem(KEY)
  } catch {
    // Không lưu được thì thôi.
  }
}
