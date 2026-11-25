import { useSyncExternalStore } from 'react'
import { checkRelease, installDownloaded, runApkUpdate, Update, type ApkUpdateState } from '@/core/native/update'

// Trạng thái tải bản mới dùng chung cho dải báo ở Chat, màn chắn bản bắt buộc và Cài đặt: bấm ở đâu cũng thấy
// cùng tiến trình, không tải hai lần.

let state: ApkUpdateState = { step: 'idle' }
const listeners = new Set<() => void>()

function set(next: ApkUpdateState) {
  state = next
  listeners.forEach((l) => l())
}

const subscribe = (l: () => void) => {
  listeners.add(l)
  return () => listeners.delete(l)
}

export const isUpdateBusy = (s: ApkUpdateState) => s.step === 'checking' || s.step === 'downloading' || s.step === 'installing'

export function startApkUpdate() {
  if (isUpdateBusy(state)) return
  void runApkUpdate({ fetchRelease: checkRelease, plugin: Update }, set)
}

// Cài tiếp tệp đã tải: sau khi bật quyền cài, hoặc người dùng lỡ hủy hộp cài.
export function continueApkInstall() {
  if (state.step !== 'need_permission' && state.step !== 'ready') return
  void installDownloaded(Update, state.path, set)
}

export function useApkUpdate(): ApkUpdateState {
  return useSyncExternalStore(subscribe, () => state)
}
