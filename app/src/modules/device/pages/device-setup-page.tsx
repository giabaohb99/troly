import { BellRing, ChevronLeft, Loader2, RefreshCw, ShieldCheck, Smartphone } from 'lucide-react'
import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Alarm } from '@/core/native/alarm'
import { Notify } from '@/core/native/notify'
import { System } from '@/core/native/system'
import { ListenedApps } from '@/modules/device/components/listened-apps'
import { SetupSteps } from '@/modules/device/components/setup-steps'
import { queryKeys } from '@/shared/constants/query-keys'
import { ErrorState } from '@/shared/components/error-state'
import { usePermissions } from '@/shared/hooks/use-permissions'
import { Button } from '@/shared/ui/button'
import { formatDayTitle, formatTime, toDateKey } from '@/shared/utils/format'

function Section({ icon: Icon, title, children }: { icon: typeof Smartphone; title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border bg-card p-4">
      <h2 className="mb-1 flex items-center gap-2 font-semibold">
        <Icon className="size-4 text-primary" />
        {title}
      </h2>
      {children}
    </section>
  )
}

function Row({ label, value, warn }: { label: string; value: ReactNode; warn?: boolean }) {
  return (
    <div className="flex justify-between gap-2 py-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={warn ? 'text-warning' : undefined}>{value}</span>
    </div>
  )
}

// Thiết lập máy và Kiểm tra máy (31 mục 3.5, luồng 2): các bước quyền, app SMS mặc định,
// trạng thái dịch vụ nghe, hàng đợi, số tin OTP đã chặn, danh sách app được nghe.
export function DeviceSetupPage() {
  const navigate = useNavigate()
  const permissions = usePermissions()
  const status = useQuery({ queryKey: queryKeys.device.notifyStatus, queryFn: async () => ({ ...(await Notify.getStatus()), checkedAt: Date.now() }), refetchInterval: 15_000 })
  const alarms = useQuery({ queryKey: queryKeys.device.alarms, queryFn: () => Alarm.getScheduled(), refetchInterval: 15_000 })
  const p = permissions.data
  const s = status.data
  const a = alarms.data
  const silentHours = s?.lastEventAt ? Math.floor((s.checkedAt - s.lastEventAt) / 3_600_000) : null

  return (
    <div className="flex flex-col gap-4 pb-8">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" aria-label="Quay lại" onClick={() => navigate(-1)}>
          <ChevronLeft className="size-5" />
        </Button>
        <h1 className="text-2xl font-bold">Thiết lập máy</h1>
      </div>

      {permissions.isError && <ErrorState error={permissions.error} onRetry={() => void permissions.refetch()} />}
      {!p && permissions.isPending && <Loader2 className="mx-auto size-6 animate-spin text-muted-foreground" />}

      {p && (
        <Section icon={ShieldCheck} title="Các bước">
          <SetupSteps permissions={p} />
          <div className="flex items-center justify-between gap-2 border-t pt-3 text-sm">
            <span>
              App SMS mặc định: <span className="font-medium">{p.defaultSmsLabel ?? 'chưa rõ'}</span>
            </span>
            <Button variant="ghost" size="sm" onClick={() => void System.openSettings({ target: 'default_apps' })}>
              Đổi
            </Button>
          </div>
        </Section>
      )}

      <Section icon={Smartphone} title="Kiểm tra máy">
        {s ? (
          <>
            <Row label="Dịch vụ nghe" value={s.listenerConnected ? 'Đang nghe' : s.listenerGranted ? 'Đã cấp, chưa kết nối' : 'Chưa bật'} warn={!s.listenerConnected} />
            <Row
              label="Tin cuối"
              value={s.lastEventAt ? `${formatDayTitle(toDateKey(new Date(s.lastEventAt))).split(', ')[1]} ${formatTime(new Date(s.lastEventAt).toISOString())}` : 'Chưa có'}
              warn={silentHours !== null && silentHours >= 24}
            />
            <Row label="Đã chặn tin OTP hôm nay" value={s.otpBlockedToday} />
            <Row label="Bỏ vì app ngoài danh sách" value={s.droppedToday} />
            <Row label="Chờ gửi" value={s.queueSize} warn={s.queueSize > 0} />
            {a && (
              <>
                <Row label="Nhắc đã đặt (14 ngày)" value={a.count} />
                {a.next[0] && <Row label="Nhắc kế tiếp" value={`${formatTime(new Date(a.next[0].fireAt).toISOString())} ${a.next[0].title}`} />}
                <Row label="Tải nhắc lần cuối" value={a.lastSyncAt ? formatTime(new Date(a.lastSyncAt).toISOString()) : 'Chưa'} warn={!a.lastSyncAt} />
                {!a.exactAllowed && <p className="mt-2 text-sm text-warning">Chưa có quyền báo thức chính xác: nhắc có thể trễ tới 10 phút.</p>}
              </>
            )}
            {!s.deviceRegistered && <p className="mt-2 text-sm text-warning">Máy chưa đăng ký với máy chủ. Đăng xuất rồi đăng nhập lại để đăng ký.</p>}
            {s.otpRejectedByServer > 0 && <p className="mt-2 text-sm text-warning">Máy chủ đã chặn {s.otpRejectedByServer} tin OTP lọt qua bộ lọc trên máy.</p>}
            <Button
              variant="secondary"
              size="sm"
              className="mt-3"
              onClick={() =>
                void Promise.all([Notify.sync(), Alarm.sync()]).then(() => {
                  toast.success('Đang gửi và tải lại danh sách, nhắc')
                  void status.refetch()
                  void alarms.refetch()
                })
              }
            >
              <RefreshCw className="size-4" />
              Gửi ngay
            </Button>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Đang đọc...</p>
        )}
      </Section>

      <Section icon={BellRing} title="App được nghe">
        <p className="mb-2 text-xs text-muted-foreground">Thông báo của app ngoài danh sách bị bỏ ngay trên điện thoại. Tin có mã OTP luôn bị bỏ.</p>
        <ListenedApps defaultSmsPackage={p?.defaultSmsPackage ?? null} defaultSmsLabel={p?.defaultSmsLabel ?? null} />
      </Section>
    </div>
  )
}
