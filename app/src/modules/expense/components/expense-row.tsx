import { ArrowLeftRight, CircleHelp, Landmark, MessageCircle, PenLine } from 'lucide-react'
import { ACCOUNT_LABELS, SOURCE_LABELS, type Expense } from '@/modules/expense/types/expense'
import { formatMoney, formatTime } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

function ExpenseIcon({ expense }: { expense: Expense }) {
  const className = 'size-4'
  if (expense.kind === 'transfer') return <ArrowLeftRight className={className} />
  if (expense.needs_review) return <CircleHelp className={className} />
  if (expense.source === 'bank_notification') return <Landmark className={className} />
  if (expense.source === 'manual') return <PenLine className={className} />
  return <MessageCircle className={className} />
}

// Một dòng chi tiêu: mã ngân hàng và 4 số cuối, không số dư (QĐ-22); chuyển nội bộ mờ, không tính tổng.
export function ExpenseRow({ expense, onClick }: { expense: Expense; onClick: () => void }) {
  const isTransfer = expense.kind === 'transfer'
  const account = expense.source === 'bank_notification' ? `${ACCOUNT_LABELS[expense.account] ?? expense.account}${expense.account_last4 ? ` ...${expense.account_last4}` : ''}` : SOURCE_LABELS[expense.source]
  const meta = isTransfer
    ? `chuyển nội bộ · ${formatTime(expense.spent_at)}`
    : [expense.category?.name ?? 'Chưa có danh mục', account, formatTime(expense.spent_at)].join(' · ')

  return (
    <button type="button" onClick={onClick} className={cn('flex w-full items-center gap-3 py-2.5 text-left', isTransfer && 'text-transfer')}>
      <span className={cn('flex size-9 shrink-0 items-center justify-center rounded-full bg-secondary', expense.needs_review && 'bg-warning/15 text-warning')}>
        <ExpenseIcon expense={expense} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{expense.merchant || (isTransfer ? 'Chuyển tiền' : 'Khoản chi')}</span>
        <span className="block truncate text-xs text-muted-foreground">{meta}</span>
      </span>
      <span className={cn('shrink-0 font-semibold tabular-nums', expense.kind === 'income' && 'text-income')}>
        {expense.kind === 'income' ? '+' : ''}
        {formatMoney(expense.amount_vnd)}
      </span>
    </button>
  )
}
