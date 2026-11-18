import { useState } from 'react'
import { Download, X } from 'lucide-react'
import { toast } from 'sonner'
import { canInstallApk, startApkDownload } from '@/core/native/update'
import { useRelease } from '@/shared/hooks/use-release'
import { Button } from '@/shared/ui/button'

// Dải báo bản APK mới ở Chat (31 luồng 5). Chỉ tải khi người dùng bấm Cập nhật (QĐ-18).
// Bản bắt buộc thì chắn cả app, chỉ còn nút Cập nhật.
export function UpdateBanner() {
  const release = useRelease()
  const [hidden, setHidden] = useState(false)
  const info = release.data
  if (!canInstallApk || !info?.update_available || !info.latest) return null

  const update = () => {
    void startApkDownload(info).then((ok) => {
      if (ok) toast.info('Đang tải bản mới. Tải xong, mở tệp để Android hỏi cài.')
    })
  }

  if (info.required) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-background px-6 text-center">
        <Download className="size-10 text-primary" />
        <h1 className="text-lg font-semibold">Cần cập nhật lên bản {info.latest.version_name}</h1>
        {info.latest.notes && <p className="text-sm text-muted-foreground">{info.latest.notes}</p>}
        <Button size="lg" onClick={update}>
          <Download className="size-4" />
          Cập nhật
        </Button>
      </div>
    )
  }

  if (hidden) return null
  return (
    <div className="flex items-center gap-2 rounded-xl border border-info/40 bg-info/10 px-3 py-2 text-sm">
      <Download className="size-4 shrink-0 text-info" />
      <span className="min-w-0 flex-1">
        Có bản {info.latest.version_name}
        {info.latest.notes ? `: ${info.latest.notes}` : ''}
      </span>
      <Button size="sm" onClick={update}>
        Cập nhật
      </Button>
      <button type="button" aria-label="Để sau" onClick={() => setHidden(true)} className="text-muted-foreground">
        <X className="size-4" />
      </button>
    </div>
  )
}
