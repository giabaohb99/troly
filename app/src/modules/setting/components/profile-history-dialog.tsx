import { useState } from 'react'
import { History, Loader2 } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { listProfileRevisions, restoreProfileRevision, type Profile } from '@/modules/setting/api/setting-api'
import { queryKeys } from '@/shared/constants/query-keys'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { formatDayTitle, formatTime, toDateKey } from '@/shared/utils/format'

const BY_LABEL: Record<string, string> = { user: 'Bạn sửa', assistant: 'Trợ lý ghi', system: 'Hệ thống' }

// Bản cũ của hồ sơ lõi (31 mục 3.5 Cài đặt): danh sách phiên bản và Khôi phục.
export function ProfileHistoryDialog({ profile, open, onOpenChange }: { profile: Profile; open: boolean; onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient()
  const [picked, setPicked] = useState<number | null>(null)
  const revisions = useQuery({ queryKey: queryKeys.setting.profileRevisions, queryFn: listProfileRevisions, enabled: open, select: (data) => data.items })
  const restore = useMutation({
    mutationFn: (version: number) => restoreProfileRevision(version, profile.version),
    onSuccess: () => {
      toast.success('Đã khôi phục bản cũ')
      void queryClient.invalidateQueries({ queryKey: queryKeys.memory.profile })
      void queryClient.invalidateQueries({ queryKey: queryKeys.setting.profileRevisions })
      onOpenChange(false)
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[85dvh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Bản cũ của hồ sơ lõi</DialogTitle>
            <DialogDescription>Khôi phục tạo một bản mới bằng nội dung cũ, không mất bản hiện tại.</DialogDescription>
          </DialogHeader>
          {revisions.isPending && <Loader2 className="mx-auto size-5 animate-spin text-muted-foreground" />}
          {revisions.isError && <p className="text-sm text-destructive">{getErrorMessage(revisions.error)}</p>}
          <ul className="divide-y">
            {(revisions.data ?? []).map((rev) => (
              <li key={rev.version} className="flex items-start gap-3 py-2.5 text-sm">
                <History className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="block">
                    Bản {rev.version} · {BY_LABEL[rev.changed_by ?? ''] ?? rev.changed_by ?? ''} · {formatDayTitle(toDateKey(rev.created_at)).split(', ')[1]} {formatTime(rev.created_at)}
                  </span>
                  {rev.reason && <span className="block text-xs text-muted-foreground">{rev.reason}</span>}
                  {rev.preview && <span className="line-clamp-2 block text-xs text-muted-foreground">{rev.preview}</span>}
                </span>
                {rev.version !== profile.version && (
                  <Button size="sm" variant="secondary" disabled={restore.isPending} onClick={() => setPicked(rev.version)}>
                    Khôi phục
                  </Button>
                )}
              </li>
            ))}
            {revisions.isSuccess && revisions.data.length === 0 && <li className="py-2 text-sm text-muted-foreground">Chưa có bản cũ.</li>}
          </ul>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={picked !== null}
        onOpenChange={(value) => !value && setPicked(null)}
        title={`Khôi phục bản ${picked ?? ''}?`}
        description="Hồ sơ lõi quay về nội dung của bản này; trợ lý dùng ngay từ lượt sau."
        confirmLabel="Khôi phục"
        danger={false}
        onConfirm={() => picked !== null && restore.mutate(picked)}
      />
    </>
  )
}
