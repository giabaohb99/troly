// Dữ liệu giả trong bộ nhớ cho chế độ `npm run dev:mock` và bài kiểm. Không dùng ở bản build thật.
import type { ChatMessage, PendingAction } from '@/modules/chat/types/chat'
import type { Category, Expense } from '@/modules/expense/types/expense'

export interface MockDb {
  messages: ChatMessage[]
  pending: PendingAction[]
  expenses: (Expense & { deleted: boolean })[]
  categories: Category[]
  notes: { id: number; title: string; body: string; created_at: string }[]
  nextId: number
  profile: { content: string; version: number }
}

const now = new Date()
const iso = (offsetMinutes: number) => new Date(now.getTime() + offsetMinutes * 60_000).toISOString()

export function createMockDb(): MockDb {
  const categories: Category[] = [
    { id: 1, name: 'Ăn uống', kind: 'expense' },
    { id: 2, name: 'Đi lại', kind: 'expense' },
    { id: 3, name: 'Mua sắm', kind: 'expense' },
    { id: 4, name: 'Hóa đơn', kind: 'expense' },
    { id: 5, name: 'Khác', kind: 'expense' },
    { id: 6, name: 'Lương', kind: 'income' },
  ]
  const expense = (id: number, amount: number, categoryId: number | null, merchant: string, minutesAgo: number, extra: Partial<Expense> = {}) => ({
    id,
    amount_vnd: amount,
    kind: 'expense' as const,
    account: 'cash',
    account_last4: null,
    to_account: null,
    to_account_last4: null,
    category: categories.find((c) => c.id === categoryId) ?? null,
    merchant,
    place: null,
    note: null,
    spent_at: iso(-minutesAgo),
    source: 'chat' as const,
    parser: 'chat',
    parse_confidence: null,
    needs_review: false,
    deleted: false,
    ...extra,
  })
  return {
    messages: [],
    pending: [],
    expenses: [
      expense(101, 45_000, 1, 'Cơm trưa', 60),
      expense(102, 120_000, 2, 'Grab', 300, { account: 'vcb', account_last4: '1234', source: 'bank_notification', parser: 'regex:vcb' }),
      expense(103, 250_000, null, 'Chưa rõ khoản', 90, { account: 'tcb', account_last4: '4821', source: 'bank_notification', needs_review: true, parse_confidence: 0.5 }),
      expense(104, 500_000, null, 'VCB sang MoMo', 1500, { kind: 'transfer', account: 'vcb', to_account: 'momo', source: 'bank_notification' }),
      expense(105, 89_000, 3, 'Shopee', 2900),
    ],
    categories,
    notes: [{ id: 1, title: 'Hợp đồng thuê nhà 2026', body: 'Gia hạn hợp đồng nhà tới 12/2027, tiền nhà 6 triệu mỗi tháng.', created_at: iso(-20_000) }],
    nextId: 1000,
    profile: { content: '# Hồ sơ lõi\n\nTên: Gia Bảo. Ở TP.HCM. Đi xe máy.', version: 3 },
  }
}

export const mockDb: MockDb = createMockDb()
