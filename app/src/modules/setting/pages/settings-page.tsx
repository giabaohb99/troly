import { useState, useSyncExternalStore, type ReactNode } from 'react'
import { BellRing, ChevronRight, MessageSquareText, Plug, Palette, Cloud, Coins, Download, FileText, History, Inbox, Loader2, LogOut, RefreshCw, Route, ShieldCheck, Smartphone } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { getAppVersion, isDebugBuild } from '@/core/config'
import { getThemePref, setThemePref, subscribeTheme, type ThemePref } from '@/core/theme'
import { canInstallApk } from '@/core/native/update'
import { useLogout, useSession } from '@/modules/auth/hooks/use-session'
import { getCostStatus, getProfile } from '@/modules/setting/api/setting-api'
import { DeviceList } from '@/modules/setting/components/device-list'
import { ProfileDialog } from '@/modules/setting/components/profile-dialog'
import { ProfileHistoryDialog } from '@/modules/setting/components/profile-history-dialog'
import { queryKeys } from '@/shared/constants/query-keys'
import { PageHeader } from '@/shared/components/page-header'
import { UpdateControls } from '@/shared/components/update-banner'
import { useApkUpdate } from '@/shared/hooks/use-apk-update'
import { needsReconnect, useGoogleStatus } from '@/shared/hooks/use-google-status'
import { useRelease } from '@/shared/hooks/use-release'
import { useFeatures } from '@/shared/hooks/use-features'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { formatUsd } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

const THEME_OPTIONS: { value: ThemePref; label: string }[] = [
  { value: 'system', label: 'Theo máy' },
  { value: 'light', label: 'Sáng' },
  { value: 'dark', label: 'Tối' },
]

function Section({ icon: Icon, title, children, action }: { icon: typeof Coins; title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="rounded-2xl border bg-card p-4">
      <h2 className="mb-3 flex items-center gap-2 font-semibold">
        <Icon className="size-4 text-primary" />
        <span className="flex-1">{title}</span>
        {action}
      </h2>
      {children}
    </section>
  )
}

function LinkRow({ icon: Icon, title, text, warn, onClick }: { icon: typeof Coins; title: string; text: string; warn?: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="flex w-full items-center gap-3 px-4 py-3 text-left">
      <Icon className="size-5 shrink-0 text-primary" />
      <span className="min-w-0 flex-1">
        <span className="block font-semibold">{title}</span>
        <span className={cn('block truncate text-sm', warn ? 'text-warning' : 'text-muted-foreground')}>{text}</span>
      </span>
      <ChevronRight className="size-4 text-muted-foreground" />
    </button>
  )
}

// Cài đặt đầy đủ (31 mục 3.5): các màn con, hồ sơ lõi và bản cũ, nhắc mặc định, chi phí AI, phiên bản, thiết bị, đăng xuất.
export function SettingsPage() {
  const navigate = useNavigate()
  const features = useFeatures()
  const session = useSession()
  const logout = useLogout()
  const profile = useQuery({ queryKey: queryKeys.memory.profile, queryFn: getProfile })
  const cost = useQuery({ queryKey: queryKeys.chat.status, queryFn: getCostStatus, staleTime: 60_000 })
  const release = useRelease()
  const google = useGoogleStatus()
  const [profileOpen, setProfileOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const version = getAppVersion()
  const theme = useSyncExternalStore(subscribeTheme, getThemePref)
  const apkUpdate = useApkUpdate()

  const checkUpdate = async () => {
    const result = await release.refetch()
    if (result.isError) toast.error('Không kiểm được bản mới, thử lại sau.')
    else if (!result.data?.update_available) toast.success('Đang dùng bản mới nhất')
  }

  const googleText = !google.data
    ? 'Lịch và việc'
    : !google.data.connected
      ? 'Chưa kết nối'
      : needsReconnect(google.data)
        ? 'Cần kết nối lại'
        : google.data.failed_outbox_count
          ? `${google.data.email} · ${google.data.failed_outbox_count} lỗi đồng bộ`
          : (google.data.email ?? 'Đã kết nối')

  return (
    <div className="flex flex-col gap-4 pb-8">
      <PageHeader title="Cài đặt" subtitle={session.data ? `${session.data.name} · ${session.data.email}` : undefined} />

      <div className="divide-y rounded-2xl border bg-card">
        <LinkRow icon={ShieldCheck} title="Thiết lập máy" text="Quyền, pin, Samsung, app được nghe, kiểm tra máy" onClick={() => navigate('/thiet-lap')} />
        <LinkRow icon={Cloud} title="Kết nối Google" text={googleText} warn={needsReconnect(google.data) || !!google.data?.failed_outbox_count} onClick={() => navigate('/cai-dat/google')} />
        <LinkRow icon={BellRing} title="Thông báo" text="Nhắc mặc định, âm thanh, giờ yên lặng, loại thông báo" onClick={() => navigate('/cai-dat/thong-bao')} />
        <LinkRow icon={Inbox} title="Hộp tin" text="Người quan trọng, từ khóa gấp, quyền đọc của trợ lý" onClick={() => navigate('/cai-dat/hop-tin')} />
        <LinkRow icon={Route} title="Lịch trình" text="Luật đánh giá chuyến, giờ phà quen" onClick={() => navigate('/cai-dat/lich-trinh')} />
        {features.zalo_bridge && <LinkRow icon={MessageSquareText} title="Zalo" text="Đăng nhập bằng mã QR để đọc, gửi tin Zalo" onClick={() => navigate('/cai-dat/zalo')} />}
        {features.connectors && <LinkRow icon={Plug} title="Kết nối" text="ERP DEGO và hệ thống khác qua MCP" onClick={() => navigate('/cai-dat/ket-noi')} />}
      </div>

      <Section
        icon={FileText}
        title="Hồ sơ lõi"
        action={
          profile.data && (
            <Button size="sm" variant="ghost" onClick={() => setHistoryOpen(true)}>
              <History className="size-4" />
              Bản cũ
            </Button>
          )
        }
      >
        <button type="button" disabled={!profile.data} onClick={() => setProfileOpen(true)} className="flex w-full items-center gap-2 text-left text-sm">
          <span className="line-clamp-2 min-w-0 flex-1 text-muted-foreground">{profile.data ? profile.data.content || 'Chưa có gì. Bấm để viết.' : profile.isError ? 'Không tải được.' : 'Đang tải...'}</span>
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
        </button>
      </Section>

      <Section icon={Palette} title="Giao diện">
        <div className="grid grid-cols-3 gap-2">
          {THEME_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              aria-pressed={theme === option.value}
              onClick={() => setThemePref(option.value)}
              className={cn('rounded-xl border py-2 text-sm', theme === option.value && 'border-primary bg-primary/15 text-primary')}
            >
              {option.label}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">Lưu trên máy này. Theo máy: đổi theo chế độ tối của điện thoại.</p>
      </Section>

      <Section
        icon={Coins}
        title="Chi phí AI"
        action={
          <Button size="sm" variant="ghost" onClick={() => navigate('/cai-dat/chi-phi')}>
            Chi tiết
            <ChevronRight className="size-4" />
          </Button>
        }
      >
        {cost.data ? (
          <div className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Tháng này</span>
              <span className="font-semibold">{formatUsd(cost.data.month_usd)}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-secondary">
              <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, (cost.data.month_usd / cost.data.monthly_warn_usd) * 100)}%` }} />
            </div>
            <p className="text-xs text-muted-foreground">
              Hôm nay {formatUsd(cost.data.today_usd)} · mức cảnh báo {formatUsd(cost.data.monthly_warn_usd)} mỗi tháng, vượt chỉ báo, không chặn.
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{cost.isError ? 'Không tải được.' : 'Đang tải...'}</p>
        )}
      </Section>

      <Section icon={Download} title="Phiên bản">
        <div className="flex flex-col gap-3 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Bản đang dùng</span>
            <span>
              {version.name} ({version.code})
            </span>
          </div>
          {release.data?.update_available && release.data.latest && (
            <div className="rounded-xl bg-info/10 p-3">
              <p className="font-medium">Có bản {release.data.latest.version_name}</p>
              {release.data.latest.notes && <p className="text-muted-foreground">{release.data.latest.notes}</p>}
              {canInstallApk && !isDebugBuild() && (
                <div className="mt-2">
                  <UpdateControls state={apkUpdate} size="sm" />
                </div>
              )}
            </div>
          )}
          {isDebugBuild() && <p className="text-xs text-muted-foreground">Bản thử: không tự kiểm bản mới, cập nhật bằng cách cài APK debug mới.</p>}
          <div className={isDebugBuild() ? 'hidden' : 'flex gap-2'}>
            <Button variant="secondary" size="sm" disabled={release.isFetching} onClick={() => void checkUpdate()}>
              {release.isFetching ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
              Kiểm tra cập nhật
            </Button>
          </div>
        </div>
      </Section>

      <Section icon={Smartphone} title="Thiết bị">
        <DeviceList />
      </Section>

      <ConfirmDialog
        title="Đăng xuất?"
        description="Lần sau mở app phải đăng nhập lại."
        confirmLabel="Đăng xuất"
        onConfirm={() => logout.mutate()}
        trigger={
          <Button variant="outline" className="w-full">
            <LogOut className="size-4" />
            Đăng xuất
          </Button>
        }
      />

      {profile.data && profileOpen && <ProfileDialog profile={profile.data} open onOpenChange={setProfileOpen} />}
      {profile.data && historyOpen && <ProfileHistoryDialog profile={profile.data} open onOpenChange={setHistoryOpen} />}
    </div>
  )
}
