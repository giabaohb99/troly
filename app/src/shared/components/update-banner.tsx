import { useState } from 'react'
import { Download, Globe, Loader2, X } from 'lucide-react'
import { canInstallApk, openDownloadPage, type ApkUpdateState } from '@/core/native/update'
import { continueApkInstall, isUpdateBusy, startApkUpdate, useApkUpdate } from '@/shared/hooks/use-apk-update'
import { useRelease } from '@/shared/hooks/use-release'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/utils/cn'

// Dải báo bản APK mới ở Chat (31 luồng 5). Chỉ tải khi người dùng bấm Cập nhật (QĐ-18); tải trong app có phần
// trăm, lỗi thì Thử lại, luôn có Tải bằng trình duyệt làm dự phòng. Bản bắt buộc thì chắn cả app.
export function UpdateBanner() {
  const release = useRelease()
  const update = useApkUpdate()
  const [hidden, setHidden] = useState(false)
  const info = release.data
  if (!canInstallApk || !info?.update_available || !info.latest) return null

  if (info.required) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-background px-6 text-center">
        <Download className="size-10 text-primary" />
        <h1 className="text-lg font-semibold">Cần cập nhật lên bản {info.latest.version_name}</h1>
        {info.latest.notes && <p className="text-sm text-muted-foreground">{info.latest.notes}</p>}
        <UpdateControls state={update} size="lg" center />
      </div>
    )
  }

  if (hidden && update.step === 'idle') return null
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-info/40 bg-info/10 px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <Download className="size-4 shrink-0 text-info" />
        <span className="min-w-0 flex-1">
          Có bản {info.latest.version_name}
          {info.latest.notes ? `: ${info.latest.notes}` : ''}
        </span>
        {!isUpdateBusy(update) && (
          <button type="button" aria-label="Để sau" onClick={() => setHidden(true)} className="text-muted-foreground">
            <X className="size-4" />
          </button>
        )}
      </div>
      <UpdateControls state={update} size="sm" />
    </div>
  )
}

// Nút và tiến trình cập nhật theo trạng thái; dùng ở dải báo, màn chắn và Cài đặt.
export function UpdateControls({ state, size, center }: { state: ApkUpdateState; size: 'sm' | 'lg'; center?: boolean }) {
  return (
    <div className={cn('flex w-full flex-col gap-2', center && 'max-w-xs items-center')}>
      {state.step === 'downloading' && (
        <div className="flex w-full flex-col gap-1">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-info/20" role="progressbar" aria-valuenow={state.percent >= 0 ? state.percent : undefined} aria-valuemin={0} aria-valuemax={100}>
            <div className={cn('h-full rounded-full bg-info transition-[width]', state.percent < 0 && 'w-1/3 animate-pulse')} style={state.percent >= 0 ? { width: `${state.percent}%` } : undefined} />
          </div>
          <span className="text-xs text-muted-foreground">{state.percent >= 0 ? `Đang tải ${state.percent}%` : 'Đang tải'}</span>
        </div>
      )}
      {state.step === 'need_permission' && (
        <p className="text-xs">
          Android cần cho phép Trợ lý cài bản mới: bật <b>Cho phép cài từ nguồn này</b> rồi quay lại, app cài tiếp.
        </p>
      )}
      {state.step === 'ready' && <p className="text-xs text-muted-foreground">Bấm Cài đặt trên hộp của Android. Lỡ đóng hộp thì bấm Cài lại.</p>}
      {state.step === 'error' && <p className="text-xs text-destructive">{state.message}</p>}
      <div className={cn('flex flex-wrap items-center gap-2', center && 'justify-center')}>
        <PrimaryButton state={state} size={size} />
        <Button size={size === 'lg' ? 'default' : 'sm'} variant="ghost" onClick={() => void openDownloadPage()}>
          <Globe className="size-4" />
          Tải bằng trình duyệt
        </Button>
      </div>
    </div>
  )
}

function PrimaryButton({ state, size }: { state: ApkUpdateState; size: 'sm' | 'lg' }) {
  switch (state.step) {
    case 'checking':
    case 'downloading':
    case 'installing':
      return (
        <Button size={size} disabled>
          <Loader2 className="size-4 animate-spin" />
          {state.step === 'installing' ? 'Đang mở trình cài' : state.step === 'checking' ? 'Đang lấy link' : 'Đang tải'}
        </Button>
      )
    case 'need_permission':
      return (
        <Button size={size} onClick={continueApkInstall}>
          Mở cài đặt
        </Button>
      )
    case 'ready':
      return (
        <Button size={size} onClick={continueApkInstall}>
          Cài lại
        </Button>
      )
    case 'error':
      return state.retry ? (
        <Button size={size} onClick={startApkUpdate}>
          Thử lại
        </Button>
      ) : null
    default:
      return (
        <Button size={size} onClick={startApkUpdate}>
          <Download className="size-4" />
          Cập nhật
        </Button>
      )
  }
}
