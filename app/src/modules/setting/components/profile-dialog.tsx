import { useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { saveProfile, type Profile } from '@/modules/setting/api/setting-api'
import { queryKeys } from '@/shared/constants/query-keys'
import { Button } from '@/shared/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { Textarea } from '@/shared/ui/textarea'
import { cn } from '@/shared/utils/cn'

const MAX_CHARS = 8000

// Sửa hồ sơ lõi (Markdown, tối đa 8.000 ký tự). Lệch phiên bản thì máy chủ trả CONFLICT.
export function ProfileDialog({ profile, open, onOpenChange }: { profile: Profile; open: boolean; onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient()
  const [content, setContent] = useState(profile.content)
  const [saving, setSaving] = useState(false)
  const savingRef = useRef(false)

  async function save() {
    if (savingRef.current || content.length > MAX_CHARS) return
    savingRef.current = true
    setSaving(true)
    try {
      const saved = await saveProfile(content, profile.version)
      queryClient.setQueryData(queryKeys.memory.profile, saved)
      toast.success('Đã lưu hồ sơ lõi')
      onOpenChange(false)
    } catch (error) {
      toast.error(getErrorMessage(error))
      void queryClient.invalidateQueries({ queryKey: queryKeys.memory.profile })
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh]">
        <DialogHeader>
          <DialogTitle>Hồ sơ lõi</DialogTitle>
          <DialogDescription>Trợ lý đọc phần này ở mọi câu trả lời.</DialogDescription>
        </DialogHeader>
        <Textarea value={content} onChange={(e) => setContent(e.target.value)} className="min-h-[50dvh] font-mono text-sm" aria-label="Nội dung hồ sơ lõi" />
        <div className="flex items-center justify-between">
          <span className={cn('text-xs text-muted-foreground', content.length > MAX_CHARS && 'text-destructive')}>
            {content.length.toLocaleString('vi-VN')}/{MAX_CHARS.toLocaleString('vi-VN')} ký tự · bản {profile.version}
          </span>
          <Button onClick={() => void save()} disabled={saving || content.length > MAX_CHARS}>
            {saving && <Loader2 className="size-4 animate-spin" />}
            Lưu
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
