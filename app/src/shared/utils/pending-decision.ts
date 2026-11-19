import { ApiError } from '@/core/api/api-error'
import type { PendingAction, PendingStatus } from '@/shared/types/pending-action'

// Kết quả hiện trên thẻ duyệt. transient: lỗi tạm (mạng, máy chủ), cho Thử lại; còn lại chỉ cho Bỏ.
export interface CardOutcome {
  status: PendingStatus
  reason: string | null
  transient: boolean
}

// Trạng thái ban đầu: lấy trạng thái máy chủ (trong hành động của tin hoặc danh sách việc chờ duyệt), không tự tính
// hết hạn theo giờ máy. Chưa biết thì coi là đang chờ; bấm mà máy chủ trả 409 thì tải lại trạng thái thật.
export function initialStatus(messageStatus: PendingStatus | null | undefined, serverStatus: PendingStatus | null | undefined): PendingStatus {
  return messageStatus ?? serverStatus ?? 'pending'
}

// Kết quả sau approve hoặc reject trả 200.
export function outcomeFromAction(action: Pick<PendingAction, 'status'> & { error?: string | null }, resultText?: string | null): CardOutcome {
  const status = action.status === 'pending' ? 'done' : action.status
  return { status, reason: status === 'failed' ? (action.error ?? resultText ?? null) : null, transient: false }
}

// Trạng thái thật đọc từ máy chủ (khi mở lại lịch sử, sau 409): giữ nguyên, kể cả pending.
export function outcomeFromServer(action: Pick<PendingAction, 'status'> & { error?: string | null }): CardOutcome {
  return { status: action.status, reason: action.status === 'failed' ? (action.error ?? null) : null, transient: false }
}

// Lỗi khi bấm: 409 (đã xử lý, hết hạn, đổi nội dung) thì tải lại trạng thái; mạng, 5xx, 429 là lỗi tạm; còn lại là
// lỗi cuối (thẻ chỉ còn Bỏ).
export function classifyDecisionError(error: unknown): 'refetch' | 'transient' | 'final' {
  if (!(error instanceof ApiError)) return 'transient'
  // Nháp thư đã bị sửa ở nơi khác (Gmail web): hiện câu lỗi, chỉ còn Bỏ; không tải lại trạng thái.
  if (error.code === 'ACTION_PAYLOAD_CHANGED') return 'final'
  if (error.status === 409) return 'refetch'
  if (error.status === 0 || error.status === 429 || error.status >= 500) return 'transient'
  return 'final'
}
