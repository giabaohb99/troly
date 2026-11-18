import { useState } from 'react'
import { Loader2, Pencil, Trash2 } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { listDevices, renameDevice, revokeDevice, type DeviceRow } from '@/modules/setting/api/setting-api'
import { queryKeys } from '@/shared/constants/query-keys'
import { STORAGE_KEYS } from '@/shared/constants/storage-keys'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { formatDayTitle, formatTime, toDateKey } from '@/shared/utils/format'

// Thiết bị (31 mục 3.5 Cài đặt): máy đã đăng nhập, đổi tên, đăng xuất máy khác (thu hồi mã thiết bị).
export function DeviceList() {
  const queryClient = useQueryClient()
  const devices = useQuery({ queryKey: queryKeys.device.list, queryFn: listDevices })
  const [currentId] = useState(() => Number(localStorage.getItem(STORAGE_KEYS.currentDeviceId)) || null)
  const [renaming, setRenaming] = useState<DeviceRow | null>(null)
  const [name, setName] = useState('')
  const [revoking, setRevoking] = useState<DeviceRow | null>(null)
  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.device.list })
  const rename = useMutation({
    mutationFn: ({ id, value }: { id: number; value: string }) => renameDevice(id, value),
    onSuccess: () => {
      setRenaming(null)
      void invalidate()
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  const revoke = useMutation({
    mutationFn: (id: number) => revokeDevice(id),
    onSuccess: () => {
      toast.success('Đã đăng xuất máy đó')
      void invalidate()
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  return (
    <>
      <ul className="flex flex-col gap-2 text-sm">
        {(devices.data?.items ?? []).map((device) => (
          <li key={device.id} className="flex items-center gap-2">
            <span className="min-w-0 flex-1">
              <span className="block truncate">
                {device.name}
                {device.id === currentId && <span className="ml-1 text-xs text-primary">máy này</span>}
              </span>
              <span className="block text-xs text-muted-foreground">
                {[device.model, device.app_version_name ? `bản ${device.app_version_name}` : null, device.last_seen_at ? `${formatDayTitle(toDateKey(device.last_seen_at)).split(', ')[1]} ${formatTime(device.last_seen_at)}` : null]
                  .filter(Boolean)
                  .join(' · ')}
              </span>
            </span>
            <Button
              size="icon"
              variant="ghost"
              aria-label={`Đổi tên ${device.name}`}
              onClick={() => {
                setName(device.name)
                setRenaming(device)
              }}
            >
              <Pencil className="size-4" />
            </Button>
            {device.id !== currentId && (
              <Button size="icon" variant="ghost" className="text-destructive" aria-label={`Đăng xuất ${device.name}`} onClick={() => setRevoking(device)}>
                <Trash2 className="size-4" />
              </Button>
            )}
          </li>
        ))}
        {devices.isSuccess && devices.data.items.length === 0 && <li className="text-muted-foreground">Chưa có điện thoại nào đăng ký.</li>}
      </ul>

      <Dialog open={!!renaming} onOpenChange={(open) => !open && setRenaming(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Đổi tên máy</DialogTitle>
            <DialogDescription>Tên hiện ở Cài đặt và Báo cáo.</DialogDescription>
          </DialogHeader>
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault()
              if (renaming && name.trim()) rename.mutate({ id: renaming.id, value: name.trim() })
            }}
          >
            <Input aria-label="Tên máy" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} autoFocus />
            <Button type="submit" disabled={rename.isPending || !name.trim()}>
              {rename.isPending && <Loader2 className="size-4 animate-spin" />}
              Lưu
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!revoking}
        onOpenChange={(open) => !open && setRevoking(null)}
        title={`Đăng xuất ${revoking?.name ?? ''}?`}
        description={`Máy đó ngừng gửi thông báo, ngừng nhận nhắc và phải đăng nhập lại.${currentId === null ? ' Nếu đây là máy đang cầm, app này cũng bị đăng xuất.' : ''}`}
        confirmLabel="Đăng xuất máy"
        onConfirm={() => revoking && revoke.mutate(revoking.id)}
      />
    </>
  )
}
