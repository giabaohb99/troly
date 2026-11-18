import { apiDelete, apiGet, apiPatch, apiPost, toQuery } from '@/core/api/http-client'
import type { Category, Expense, ExpenseInput, ExpenseSummary, Period } from '@/modules/expense/types/expense'

export interface ExpenseFilters {
  from: string
  to: string
  categoryId: number | null
  needsReview?: boolean
}

export const listExpenses = (filters: ExpenseFilters, cursor: string | null) =>
  apiGet<{ items: Expense[]; next_cursor: string | null }>(
    `/expenses${toQuery({ from: filters.from, to: filters.to, category_id: filters.categoryId, needs_review: filters.needsReview, cursor, limit: 50 })}`,
  )

export const getSummary = (period: Period) => apiGet<ExpenseSummary>(`/expenses/summary${toQuery({ period })}`)
export const listCategories = () => apiGet<{ items: Category[] }>('/expenses/categories')
export const createExpense = (input: ExpenseInput) => apiPost<Expense>('/expenses', input)
export const updateExpense = (id: number, input: Partial<ExpenseInput>) => apiPatch<Expense>(`/expenses/${id}`, input)
export const deleteExpense = (id: number) => apiDelete<null>(`/expenses/${id}`)
export const restoreExpense = (id: number) => apiPost<Expense>(`/expenses/${id}/restore`)
export const getExpense = (id: number) => apiGet<Expense>(`/expenses/${id}`)
