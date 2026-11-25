import { useEffect, useState } from 'react'
import { CircleCheck, Loader2, LogOut, QrCode, RefreshCw, TriangleAlert } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { SettingSection, SubPage } from '@/modules/setting/components/sub-page'
import { isZaloWaiting, startZaloLogin, useZaloStatus, ZALO_STATUS_KEY, zaloLogout, zaloStateText, type ZaloStatus } from '@/shared/api/zalo-api'
import { ErrorState } from '@/shared/components/error-state'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { formatTime } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

// Giây còn lại của mã QR (đếm lùi trên màn).
function useSecondsLeft(expiresAt: string | null | undefined): number | null {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!expiresAt) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [expiresAt])
  if (!expiresAt) return null
  return Math.max(0, Math.round((Date.parse(expiresAt) - now) / 1000))
}

// Cài đặt → Zalo (QĐ-52): đăng nhập bằng mã QR hiện trong app (quét bằng Zalo trên máy khác), hỏi trạng thái mỗi 2
// giây tới khi đăng nhập; báo bị đá khi mở Zalo Web nơi khác; Đăng xuất từ xa. Phiên Zalo lưu trên máy chủ.
export function ZaloSettingsPage() {
  const queryClient = useQueryClient()
  const status = useZaloStatus()
  const data = status.data
  const secondsLeft = useSecondsLeft(data?.state === 'waiting_scan' ? data.qr_expires_at : null)
  const apply = (next: ZaloStatus) => queryClient.setQueryData(ZALO_STATUS_KEY, (old: ZaloStatus | undefined) => ({ ...(old ?? { account: null }), ...next }))

  const login = useMutation({
    mutationFn: startZaloLogin,
    onSuccess: apply,
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  const logout = useMutation({
    mutationFn: zaloLogout,
    onSuccess: (next) => {
      apply({ ...next, account: null })
      toast.success('Đã đăng xuất Zalo')
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  // Vừa đăng nhập xong: báo một lần.
  const [wasWaiting, setWasWaiting] = useState(false)
  useEffect(() => {
    if (isZaloWaiting(data?.state)) setWasWaiting(true)
    else if (wasWaiting && data?.state === 'logged_in') {
      setWasWaiting(false)
      toast.success('Đã đăng nhập Zalo')
    }
  }, [data?.state, wasWaiting])

  const expired = data?.state === 'expired' || (data?.state === 'waiting_scan' && secondsLeft === 0)
  const warn = data && ['kicked', 'error', 'unavailable', 'expired'].includes(data.state)

  return (
    <SubPage title="Zalo" subtitle="Đọc và gửi tin Zalo trong app">
      {status.isPending && <SkeletonList />}
      {status.isError && <ErrorState error={status.error} onRetry={() => void status.refetch()} />}
      {data && (
        <>
          <SettingSection title="Tài khoản">
            <p className={cn('flex items-start gap-2 text-sm', data.state === 'logged_in' ? 'text-primary' : warn ? 'text-warning' : 'text-muted-foreground')}>
              {data.state === 'logged_in' ? <CircleCheck className="mt-0.5 size-4 shrink-0" /> : warn ? <TriangleAlert className="mt-0.5 size-4 shrink-0" /> : <QrCode className="mt-0.5 size-4 shrink-0" />}
              {zaloStateText(data)}
            </p>
            {data.state === 'logged_in' && data.last_event_at && <p className="mt-1 text-xs text-muted-foreground">Tin cuối nhận lúc {formatTime(data.last_event_at)}</p>}

            {data.state === 'waiting_scan' && data.qr_png_base64 && !expired && (
              <div className="mt-3 flex flex-col items-center gap-2">
                <img src={`data:image/png;base64,${data.qr_png_base64}`} alt="Mã QR đăng nhập Zalo" className="size-56 rounded-xl border bg-white p-2" />
                {secondsLeft !== null && <p className="text-xs text-muted-foreground tabular-nums">Mã còn {secondsLeft} giây</p>}
              </div>
            )}
            {data.state === 'scanned' && (
              <p className="mt-3 flex items-center gap-2 text-sm">
                <Loader2 className="size-4 animate-spin" />
                Chờ bấm Đồng ý trong Zalo...
              </p>
            )}

            <div className="mt-3 flex flex-wrap gap-2">
              {data.state !== 'logged_in' && !isZaloWaiting(data.state) && data.state !== 'unavailable' && (
                <Button disabled={login.isPending} onClick={() => login.mutate()}>
                  {login.isPending ? <Loader2 className="size-4 animate-spin" /> : <QrCode className="size-4" />}
                  Đăng nhập bằng mã QR
                </Button>
              )}
              {expired && data.state === 'waiting_scan' && (
                <Button disabled={login.isPending} onClick={() => login.mutate()}>
                  <RefreshCw className="size-4" />
                  Tạo mã mới
                </Button>
              )}
              {data.state === 'logged_in' && (
                <ConfirmDialog
                  title="Đăng xuất Zalo?"
                  description="Trợ lý thôi đọc và gửi tin Zalo cho tới khi quét mã lại. Tin đã lưu trong Hộp tin vẫn giữ."
                  confirmLabel="Đăng xuất"
                  onConfirm={() => logout.mutate()}
                  trigger={
                    <Button variant="outline" disabled={logout.isPending}>
                      <LogOut className="size-4" />
                      Đăng xuất
                    </Button>
                  }
                />
              )}
            </div>
          </SettingSection>
          <p className="px-1 text-xs text-muted-foreground">
            Dùng thư viện Zalo không chính thức (đã chấp nhận rủi ro tài khoản bị hạn chế, QĐ-52). Mở Zalo Web ở nơi khác sẽ làm trợ lý bị đăng xuất tạm. Tin một-một chỉ có từ lúc đăng nhập; nhóm lấy được tin cũ.
          </p>
        </>
      )}
    </SubPage>
  )
}
