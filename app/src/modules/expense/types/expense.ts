// Theo 12-api.md mục 5.4 và 11-co-so-du-lieu.md bảng tab_expense. Không có số dư (QĐ-22).

export type ExpenseKind = 'expense' | 'income' | 'transfer'
export type ExpenseSource = 'chat' | 'bank_notification' | 'manual'

export interface Category {
  id: number
  name: string
  kind: 'expense' | 'income'
}

export interface Expense {
  id: number
  amount_vnd: number
  kind: ExpenseKind
  account: string
  account_last4: string | null
  to_account: string | null
  to_account_last4: string | null
  category: Category | null
  merchant: string | null
  place: string | null
  note: string | null
  spent_at: string
  source: ExpenseSource
  parser: string | null
  parse_confidence: number | null
  needs_review: boolean
}

export interface ExpenseInput {
  amount_vnd: number
  kind: ExpenseKind
  account: string
  category_id: number | null
  merchant: string | null
  note: string | null
  spent_at: string
}

export interface ExpenseSummary {
  from: string
  to: string
  total_expense_vnd: number
  total_income_vnd: number
  total_transfer_vnd: number
  groups: { key: string; label: string; total_vnd: number }[]
}

export type Period = 'day' | 'week' | 'month'

export const ACCOUNT_LABELS: Record<string, string> = {
  vcb: 'VCB',
  tcb: 'TCB',
  momo: 'MoMo',
  cash: 'Tiền mặt',
  card: 'Thẻ',
  other: 'Khác',
}

export const SOURCE_LABELS: Record<ExpenseSource, string> = {
  chat: 'chat',
  bank_notification: 'ngân hàng',
  manual: 'ghi tay',
}
