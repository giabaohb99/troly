import { apiGet, apiPost } from '@/core/api/http-client'
import type { PendingAction } from '@/shared/types/pending-action'

// Duyệt chỉ bằng nút (31 mục 3.3): máy chủ chạy đúng nội dung đã lưu, không qua Claude.
export const approveAction = (id: number) => apiPost<{ action: PendingAction; result_text: string | null }>(`/chat/actions/${id}/approve`)
// Trạng thái thật của một việc chờ duyệt (sau 409 hoặc khi mở lại lịch sử). Không thấy thì coi là hết hạn.
export async function getActionStatus(id: number): Promise<PendingAction> {
  const data = await apiGet<{ items: PendingAction[] }>('/chat/actions?status=pending,done,failed,rejected,expired')
  return data.items.find((a) => a.id === id) ?? ({ id, status: 'expired' } as PendingAction)
}
export const rejectAction = (id: number) => apiPost<{ action: PendingAction }>(`/chat/actions/${id}/reject`)
