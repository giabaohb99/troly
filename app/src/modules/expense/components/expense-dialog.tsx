import { useRef, useState, type FormEvent } from 'react'
import { Loader2, Trash2 } from 'lucide-react'
import { getErrorMessage } from '@/core/api/api-error'
import { ExpenseSourceBlock } from '@/modules/expense/components/expense-source'
import { useCategories, useDeleteExpense, useSaveExpense } from '@/modules/expense/hooks/use-expenses'
import type { Expense, ExpenseKind } from '@/modules/expense/types/expense'
import { fromLocalInput, toLocalInput } from '@/modules/expense/utils/period-range'
import { Button } from '@/shared/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { formatMoney, parseMoney } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

interface ExpenseDialogProps {
  expense: Expense | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

// Hộp sửa và ghi tay (31 mục 3.5). Mỗi lần mở dựng lại từ đầu (key ở chỗ gọi) nên không cần đồng bộ state.
export function ExpenseDialog({ expense, open, onOpenChange }: ExpenseDialogProps) {
  const categories = useCategories()
  const save = useSaveExpense()
  const remove = useDeleteExpense()
  const [amountText, setAmountText] = useState(expense ? String(expense.amount_vnd) : '')
  const [kind, setKind] = useState<ExpenseKind>(expense?.kind === 'income' ? 'income' : 'expense')
  const [merchant, setMerchant] = useState(expense?.merchant ?? '')
  const [categoryId, setCategoryId] = useState<number | null>(expense?.category?.id ?? null)
  const [note, setNote] = useState(expense?.note ?? '')
  const [spentAt, setSpentAt] = useState(() => toLocalInput(expense?.spent_at ?? new Date().toISOString()))
  const [error, setError] = useState('')
  const savingRef = useRef(false)
  const amount = parseMoney(amountText)
  const isTransfer = expense?.kind === 'transfer'

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (savingRef.current) return
    if (!amount) {
      setError('Số tiền chưa đúng, ví dụ 45k hoặc 45.000.')
      return
    }
    savingRef.current = true
    setError('')
    try {
      await save.mutateAsync({
        id: expense?.id ?? null,
        input: {
          amount_vnd: amount,
          kind: isTransfer ? 'transfer' : kind,
          account: expense?.account ?? 'cash',
          category_id: categoryId,
          merchant: merchant.trim() || null,
          note: note.trim() || null,
          spent_at: fromLocalInput(spentAt),
        },
      })
      onOpenChange(false)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      savingRef.current = false
    }
  }

  const visibleCategories = (categories.data ?? []).filter((c) => c.kind === (kind === 'income' ? 'income' : 'expense'))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{expense ? 'Sửa khoản' : 'Ghi tay'}</DialogTitle>
          <DialogDescription>{isTransfer ? 'Chuyển nội bộ, không tính vào tổng chi.' : 'Gõ 45k, 1,2tr cũng được.'}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {!isTransfer && (
            <div className="grid grid-cols-2 gap-2">
              {(['expense', 'income'] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setKind(value)}
                  className={cn('rounded-xl border py-2 text-sm', kind === value && 'border-primary bg-primary/15 text-primary')}
                >
                  {value === 'expense' ? 'Chi' : 'Thu'}
                </button>
              ))}
            </div>
          )}
          <div className="flex flex-col gap-2">
            <Label htmlFor="amount">Số tiền</Label>
            <Input id="amount" inputMode="decimal" autoComplete="off" value={amountText} onChange={(e) => setAmountText(e.target.value)} placeholder="45k" required />
            {amount !== null && <p className="text-xs text-muted-foreground">{formatMoney(amount)}</p>}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="merchant">Khoản</Label>
            <Input id="merchant" value={merchant} onChange={(e) => setMerchant(e.target.value)} placeholder="Cơm trưa" maxLength={200} />
          </div>
          {!isTransfer && (
            <div className="flex flex-col gap-2">
              <Label>Danh mục</Label>
              <div className="flex flex-wrap gap-2">
                {visibleCategories.map((category) => (
                  <button
                    key={category.id}
                    type="button"
                    onClick={() => setCategoryId(category.id === categoryId ? null : category.id)}
                    className={cn('rounded-full border px-3 py-1 text-sm', category.id === categoryId && 'border-primary bg-primary/15 text-primary')}
                  >
                    {category.name}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="flex flex-col gap-2">
            <Label htmlFor="spent-at">Thời điểm</Label>
            <Input id="spent-at" type="datetime-local" value={spentAt} onChange={(e) => setSpentAt(e.target.value)} required />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="note">Ghi chú</Label>
            <Input id="note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
          </div>
          {expense?.source === 'bank_notification' && <ExpenseSourceBlock expenseId={expense.id} />}
          {error && (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            {expense && (
              <Button
                type="button"
                variant="ghost"
                className="text-destructive"
                onClick={() => {
                  remove.mutate(expense.id)
                  onOpenChange(false)
                }}
              >
                <Trash2 className="size-4" />
                Xóa
              </Button>
            )}
            <Button type="submit" className="ml-auto" disabled={save.isPending}>
              {save.isPending && <Loader2 className="size-4 animate-spin" />}
              Lưu
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
