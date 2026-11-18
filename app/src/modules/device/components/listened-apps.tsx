import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { isNative } from '@/core/config'
import { Notify } from '@/core/native/notify'
import { System } from '@/core/native/system'
import { listListenedApps, setListenedAppEnabled, SMS_DEFAULT, type ListenedAppRow } from '@/modules/device/api/device-api'
import { queryKeys } from '@/shared/constants/query-keys'
import { ErrorState } from '@/shared/components/error-state'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { Switch } from '@/shared/ui/switch'

// App được nghe (31 mục 3.5 Cài đặt): bật tắt từng app; đổi danh sách chỉ ở đây, không qua trợ lý.
export function ListenedApps({ defaultSmsPackage, defaultSmsLabel }: { defaultSmsPackage: string | null; defaultSmsLabel: string | null }) {
  const queryClient = useQueryClient()
  const apps = useQuery({ queryKey: queryKeys.device.listenedApps, queryFn: listListenedApps, select: (d) => d.items })
  const packages = (apps.data ?? []).map((a) => (a.package_name === SMS_DEFAULT ? defaultSmsPackage : a.package_name)).filter((p): p is string => Boolean(p))
  const installed = useQuery({
    queryKey: [...queryKeys.device.listenedApps, 'installed', packages.join(',')],
    queryFn: () => System.getInstalledApps({ packages }),
    enabled: packages.length > 0,
  })

  async function toggle(app: ListenedAppRow, enabled: boolean) {
    try {
      await setListenedAppEnabled(app.id, enabled)
      await queryClient.invalidateQueries({ queryKey: queryKeys.device.listenedApps })
      // Plugin tải lại danh sách ngay, không chờ nhịp tim 6 giờ.
      if (isNative) await Notify.sync()
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  if (apps.isPending) return <SkeletonList rows={3} />
  if (apps.isError) return <ErrorState error={apps.error} onRetry={() => void apps.refetch()} />

  return (
    <ul className="flex flex-col divide-y">
      {apps.data.map((app) => {
        const isSms = app.package_name === SMS_DEFAULT
        const pkg = isSms ? defaultSmsPackage : app.package_name
        const label = isSms ? `SMS (${defaultSmsLabel ?? 'app mặc định'})` : app.label
        const present = !pkg || !installed.data ? null : installed.data.installed.includes(pkg)
        return (
          <li key={app.id} className="flex items-center gap-3 py-2.5">
            <div className="min-w-0 flex-1">
              <p className="font-medium">{label}</p>
              <p className="text-xs text-muted-foreground">
                {app.purpose === 'expense' ? 'Chi tiêu' : 'Hộp tin'}
                {present === false && ' · Không thấy trên máy'}
              </p>
            </div>
            <Switch checked={app.enabled} onCheckedChange={(value) => void toggle(app, value)} aria-label={`Nghe ${label}`} />
          </li>
        )
      })}
    </ul>
  )
}
