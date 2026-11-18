import { useState, type ReactNode } from 'react'
import { ChevronRight, Coins, Download, FileText, Loader2, LogOut, RefreshCw, ShieldCheck, Smartphone } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { getAppVersion } from '@/core/config'
import { canInstallApk, startApkDownload } from '@/core/native/update'
import { useLogout, useSession } from '@/modules/auth/hooks/use-session'
import { getCostStatus, getProfile, listDevices } from '@/modules/setting/api/setting-api'
import { ProfileDialog } from '@/modules/setting/components/profile-dialog'
import { queryKeys } from '@/shared/constants/query-keys'
import { PageHeader } from '@/shared/components/page-header'
import { useRelease } from '@/shared/hooks/use-release'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { formatDayTitle, formatTime, formatUsd, toDateKey } from '@/shared/utils/format'

function Section({ icon: Icon, title, children }: { icon: typeof Coins; title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border bg-card p-4">
      <h2 className="mb-3 flex items-center gap-2 font-semibold">
        <Icon className="size-4 text-primary" />
        {title}
      </h2>
      {children}
    </section>
  )
}

// Cài đặt Phase 1 (31 mục 3.5): hồ sơ lõi, chi phí AI, phiên bản, thiết bị, đăng xuất.
export function SettingsPage() {
  const navigate = useNavigate()
  const session = useSession()
  const logout = useLogout()
  const profile = useQuery({ queryKey: queryKeys.memory.profile, queryFn: getProfile })
  const cost = useQuery({ queryKey: queryKeys.chat.status, queryFn: getCostStatus, staleTime: 60_000 })
  const devices = useQuery({ queryKey: queryKeys.device.list, queryFn: listDevices })
  const release = useRelease()
  const [profileOpen, setProfileOpen] = useState(false)
  const version = getAppVersion()

  const checkUpdate = async () => {
    const result = await release.refetch()
    if (result.isError) toast.error('Không kiểm được bản mới, thử lại sau.')
    else if (!result.data?.update_available) toast.success('Đang dùng bản mới nhất')
  }

  return (
    <div className="flex flex-col gap-4 pb-8">
      <PageHeader title="Cài đặt" subtitle={session.data ? `${session.data.name} · ${session.data.email}` : undefined} />

      <button type="button" onClick={() => navigate('/thiet-lap')} className="flex items-center gap-3 rounded-2xl border bg-card p-4 text-left">
        <ShieldCheck className="size-5 shrink-0 text-primary" />
        <span className="min-w-0 flex-1">
          <span className="block font-semibold">Thiết lập máy</span>
          <span className="block text-sm text-muted-foreground">Quyền đọc thông báo, pin, Samsung, app được nghe</span>
        </span>
        <ChevronRight className="size-4 text-muted-foreground" />
      </button>

      <Section icon={FileText} title="Hồ sơ lõi">
        <button type="button" disabled={!profile.data} onClick={() => setProfileOpen(true)} className="flex w-full items-center gap-2 text-left text-sm">
          <span className="line-clamp-2 min-w-0 flex-1 text-muted-foreground">{profile.data ? profile.data.content || 'Chưa có gì. Bấm để viết.' : profile.isError ? 'Không tải được.' : 'Đang tải...'}</span>
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
        </button>
      </Section>

      <Section icon={Coins} title="Chi phí AI">
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
            </div>
          )}
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" disabled={release.isFetching} onClick={() => void checkUpdate()}>
              {release.isFetching ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
              Kiểm tra cập nhật
            </Button>
            {canInstallApk && release.data?.update_available && (
              <Button size="sm" onClick={() => void startApkDownload(release.data)}>
                <Download className="size-4" />
                Cập nhật
              </Button>
            )}
          </div>
        </div>
      </Section>

      <Section icon={Smartphone} title="Thiết bị">
        <ul className="flex flex-col gap-2 text-sm">
          {(devices.data?.items ?? []).map((device) => (
            <li key={device.id} className="flex justify-between gap-2">
              <span>
                {device.name}
                {device.model ? ` · ${device.model}` : ''}
              </span>
              <span className="text-xs text-muted-foreground">
                {device.last_seen_at ? `${formatDayTitle(toDateKey(device.last_seen_at)).split(', ')[1]} ${formatTime(device.last_seen_at)}` : ''}
              </span>
            </li>
          ))}
          {devices.isSuccess && devices.data.items.length === 0 && <li className="text-muted-foreground">Chưa có điện thoại nào đăng ký.</li>}
        </ul>
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
    </div>
  )
}
