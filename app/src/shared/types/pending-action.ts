// Việc chờ duyệt (12 mục 5.2): dùng chung cho thẻ duyệt trong chat và trong hộp sửa sự kiện có khách.

export type PendingStatus = 'pending' | 'done' | 'failed' | 'rejected' | 'expired'

export interface PendingAction {
  id: number
  tool_name: string
  title: string
  summary: string
  details: { label: string; value: string }[]
  danger: boolean
  status: PendingStatus
  expires_at: string
  created_at: string
}

// Phần thẻ duyệt cần để hiện; hành động `confirm` của chat và PendingAction đều đổi được về đây.
export interface ConfirmInfo {
  pending_action_id: number
  title: string
  summary: string
  details: { label: string; value: string }[]
  confirm_label: string
  cancel_label: string
  danger: boolean
  expires_at: string
}

export function toConfirmInfo(action: PendingAction, labels: { confirm?: string; cancel?: string } = {}): ConfirmInfo {
  return {
    pending_action_id: action.id,
    title: action.title,
    summary: action.summary,
    details: action.details,
    confirm_label: labels.confirm ?? '',
    cancel_label: labels.cancel ?? '',
    danger: action.danger,
    expires_at: action.expires_at,
  }
}
