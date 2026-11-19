import { toConfirmInfo, type ConfirmInfo, type PendingAction } from '@/shared/types/pending-action'

// Thẻ duyệt gửi thư: dùng thẻ confirm máy chủ dựng sẵn nếu có, không thì dựng từ PendingAction.
export function confirmOfPending(pending: PendingAction & { action?: unknown }, recipients: number): ConfirmInfo {
  const built = pending.action as Partial<ConfirmInfo> | undefined
  const label = recipients > 1 ? `Gửi tới ${recipients} người` : 'Gửi thư'
  if (built && typeof built.pending_action_id === 'number') return { ...(built as ConfirmInfo), confirm_label: built.confirm_label || label }
  return toConfirmInfo(pending, { confirm: label })
}
