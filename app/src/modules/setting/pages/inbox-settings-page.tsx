import { useState, type FormEvent } from 'react'
import { Loader2, Star, X, Zap } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { createInboxRule, deleteInboxRule, listInboxRules, type InboxRule } from '@/modules/setting/api/setting-api'
import { SettingSection, SubPage } from '@/modules/setting/components/sub-page'
import { usePatchSettings, useSettings } from '@/modules/setting/hooks/use-settings'
import { ListenedApps } from '@/shared/components/listened-apps'
import { queryKeys } from '@/shared/constants/query-keys'
import { usePermissions } from '@/shared/hooks/use-permissions'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Switch } from '@/shared/ui/switch'

function RuleList({ kind, rules, placeholder, icon: Icon }: { kind: 'vip_sender' | 'urgent_keyword'; rules: InboxRule[]; placeholder: string; icon: typeof Star }) {
  const queryClient = useQueryClient()
  const [value, setValue] = useState('')
  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.setting.inboxRules })
  const add = useMutation({
    mutationFn: (text: string) => createInboxRule(kind, text),
    onSuccess: () => {
      setValue('')
      void invalidate()
      void queryClient.invalidateQueries({ queryKey: queryKeys.inbox.all })
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  const remove = useMutation({
    mutationFn: (id: number) => deleteInboxRule(id),
    onSuccess: () => invalidate(),
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (value.trim()) add.mutate(value.trim())
  }
  return (
    <div className="flex flex-col gap-3">
      {rules.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {rules.map((rule) => (
            <span key={rule.id} className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-sm">
              <Icon className="size-3.5 text-primary" />
              {rule.value}
              <button type="button" aria-label={`Bỏ ${rule.value}`} disabled={remove.isPending} onClick={() => remove.mutate(rule.id)}>
                <X className="size-3.5" />
              </button>
            </span>
          ))}
        </div>
      )}
      <form onSubmit={submit} className="flex gap-2">
        <Input value={value} onChange={(e) => setValue(e.target.value)} placeholder={placeholder} maxLength={200} />
        <Button type="submit" variant="secondary" disabled={add.isPending || !value.trim()}>
          {add.isPending && <Loader2 className="size-4 animate-spin" />}
          Thêm
        </Button>
      </form>
    </div>
  )
}

// Hộp tin trong Cài đặt (31 mục 3.5): cho trợ lý đọc hộp tin, người quan trọng, từ khóa gấp.
export function InboxSettingsPage() {
  const settings = useSettings()
  const patch = usePatchSettings()
  const permissions = usePermissions()
  const rules = useQuery({ queryKey: queryKeys.setting.inboxRules, queryFn: listInboxRules, select: (data) => data.items })
  const aiEnabled = settings.data?.['inbox.ai_enabled'] ?? true
  return (
    <SubPage title="Hộp tin" subtitle="Người quan trọng, từ khóa gấp, quyền đọc của trợ lý">
      <SettingSection title="Trợ lý">
        <label className="flex items-start justify-between gap-3 text-sm">
          <span>
            <span className="block font-medium">Cho trợ lý đọc hộp tin</span>
            <span className="block text-muted-foreground">Tắt thì trợ lý không tóm tắt, không tìm trong tin nhắn. Cuộc trò chuyện riêng tư không bao giờ ra trợ lý.</span>
          </span>
          <Switch checked={aiEnabled} disabled={!settings.data || patch.isPending} onCheckedChange={(on) => patch.mutate({ 'inbox.ai_enabled': on })} aria-label="Cho trợ lý đọc hộp tin" />
        </label>
      </SettingSection>
      <SettingSection title="App được nghe">
        <p className="mb-2 text-sm text-muted-foreground">Telegram, Messenger mặc định tắt; bật lại ở đây nếu cần. Tin có mã OTP luôn bị bỏ.</p>
        <ListenedApps defaultSmsPackage={permissions.data?.defaultSmsPackage ?? null} defaultSmsLabel={permissions.data?.defaultSmsLabel ?? null} />
      </SettingSection>
      <SettingSection title="Người quan trọng">
        <p className="mb-3 text-sm text-muted-foreground">Tin của những người này luôn lên mục Quan trọng. Ghi đúng tên hiện trên thông báo.</p>
        <RuleList kind="vip_sender" rules={(rules.data ?? []).filter((r) => r.kind === 'vip_sender')} placeholder="Ví dụ: Anh Hùng" icon={Star} />
      </SettingSection>
      <SettingSection title="Từ khóa gấp">
        <p className="mb-3 text-sm text-muted-foreground">Tin có những chữ này được đánh dấu gấp, không phân biệt dấu.</p>
        <RuleList kind="urgent_keyword" rules={(rules.data ?? []).filter((r) => r.kind === 'urgent_keyword')} placeholder="Ví dụ: khẩn" icon={Zap} />
      </SettingSection>
    </SubPage>
  )
}
