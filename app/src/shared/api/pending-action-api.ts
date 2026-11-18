import { apiPost } from '@/core/api/http-client'
import type { PendingAction } from '@/shared/types/pending-action'

// Duyệt chỉ bằng nút (31 mục 3.3): máy chủ chạy đúng nội dung đã lưu, không qua Claude.
export const approveAction = (id: number) => apiPost<{ action: PendingAction; result_text: string | null }>(`/chat/actions/${id}/approve`)
export const rejectAction = (id: number) => apiPost<{ action: PendingAction }>(`/chat/actions/${id}/reject`)
