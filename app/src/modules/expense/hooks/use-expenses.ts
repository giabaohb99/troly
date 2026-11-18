import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { createExpense, deleteExpense, getSummary, listCategories, listExpenses, restoreExpense, updateExpense, type ExpenseFilters } from '@/modules/expense/api/expense-api'
import type { ExpenseInput, Period } from '@/modules/expense/types/expense'
import { queryKeys } from '@/shared/constants/query-keys'

export function useExpenseList(filters: ExpenseFilters) {
  return useInfiniteQuery({
    queryKey: queryKeys.expense.list({ ...filters }),
    queryFn: ({ pageParam }) => listExpenses(filters, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  })
}

export function useExpenseSummary(period: Period) {
  return useQuery({ queryKey: queryKeys.expense.summary(period), queryFn: () => getSummary(period) })
}

export function useCategories() {
  return useQuery({ queryKey: queryKeys.expense.categories, queryFn: listCategories, staleTime: 10 * 60_000, select: (data) => data.items })
}

function useInvalidateExpenses() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.expense.all })
}

export function useSaveExpense() {
  const invalidate = useInvalidateExpenses()
  return useMutation({
    mutationFn: ({ id, input }: { id: number | null; input: ExpenseInput }) => (id ? updateExpense(id, input) : createExpense(input)),
    onSuccess: () => invalidate(),
  })
}

// Xóa một dòng làm ngay, toast có Hoàn tác (QĐ-27).
export function useDeleteExpense() {
  const invalidate = useInvalidateExpenses()
  return useMutation({
    mutationFn: (id: number) => deleteExpense(id),
    onSuccess: (_data, id) => {
      void invalidate()
      toast.success('Đã xóa khoản chi', {
        duration: 8_000,
        action: {
          label: 'Hoàn tác',
          onClick: () =>
            void restoreExpense(id)
              .then(() => invalidate())
              .catch((error: unknown) => toast.error(getErrorMessage(error))),
        },
      })
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
}
