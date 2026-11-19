import { ApiError } from '@/core/api/api-error'
import type { PendingAction, PendingStatus } from '@/shared/types/pending-action'
import { formatTime, toDateKey } from '@/shared/utils/format'

// Kết quả hiện trên thẻ duyệt. transient: lỗi tạm (mạng, máy chủ), cho Thử lại; còn lại chỉ cho Bỏ.
export interface CardOutcome {
  status: PendingStatus
  reason: string | null
  transient: boolean
  // Giờ máy chủ quyết và câu kết quả máy chủ trả (khi có).
  decidedAt?: string | null
  resultText?: string | null
}

type ServerAction = Pick<PendingAction, 'status'> & { error?: string | null; decided_at?: string | null }

// Chỉ trạng thái đã quyết (khác pending) mới tin được từ bản tin: tin trong cache hoặc tin cũ giữ trong bộ nhớ có
// thể chụp lúc thẻ còn chờ. Pending hoặc chưa biết thì hỏi máy chủ trước khi hiện nút (lỗi bản 1.0.4).
export function isFinalStatus(status: PendingStatus | null | undefined): boolean {
  return !!status && status !== 'pending'
}

// Câu kết quả đáng hiện thêm (ví dụ *Đã không còn, không cần xóa.*); câu chung chung thì bỏ.
const GENERIC_RESULTS = new Set(['đã làm xong.', 'thành công', 'đã bỏ.', ''])
export function extraResult(text: string | null | undefined): string | null {
  const t = text?.trim() ?? ''
  return GENERIC_RESULTS.has(t.toLowerCase()) ? null : t
}

// *lúc 10:53* trong ngày, *lúc 10:53 18/11* ngày khác; không có giờ máy chủ thì không hiện giờ.
export function decidedLabel(decidedAt: string | null | undefined, todayKey: string = toDateKey(new Date())): string {
  if (!decidedAt || Number.isNaN(Date.parse(decidedAt))) return ''
  const key = toDateKey(decidedAt)
  if (key === todayKey) return `lúc ${formatTime(decidedAt)}`
  const [, m, d] = key.split('-')
  return `lúc ${formatTime(decidedAt)} ${d}/${m}`
}

// Trạng thái ban đầu: lấy trạng thái máy chủ (trong hành động của tin hoặc danh sách việc chờ duyệt), không tự tính
// hết hạn theo giờ máy. Chưa biết thì coi là đang chờ; bấm mà máy chủ trả 409 thì tải lại trạng thái thật.
export function initialStatus(messageStatus: PendingStatus | null | undefined, serverStatus: PendingStatus | null | undefined): PendingStatus {
  return messageStatus ?? serverStatus ?? 'pending'
}

// Kết quả sau approve hoặc reject trả 200.
// Bấm lại thẻ đã quyết thì máy chủ trả 200 kèm trạng thái và decided_at cũ: hiện đúng giờ đó.
export function outcomeFromAction(action: ServerAction, resultText?: string | null): CardOutcome {
  const status = action.status === 'pending' ? 'done' : action.status
  return {
    status,
    reason: status === 'failed' ? (action.error ?? resultText ?? null) : null,
    transient: false,
    decidedAt: action.decided_at ?? null,
    resultText: resultText ?? null,
  }
}

// Trạng thái thật đọc từ máy chủ (khi mở lại lịch sử, sau 409): giữ nguyên, kể cả pending.
export function outcomeFromServer(action: ServerAction): CardOutcome {
  return { status: action.status, reason: action.status === 'failed' ? (action.error ?? null) : null, transient: false, decidedAt: action.decided_at ?? null }
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
