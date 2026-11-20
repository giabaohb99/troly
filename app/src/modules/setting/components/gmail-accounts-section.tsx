import { useState } from 'react'
import { Browser } from '@capacitor/browser'
import { CircleCheck, Loader2, Mail, Plus, TriangleAlert } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { isNative } from '@/core/config'
import { usePatchSettings, useSettings } from '@/modules/setting/hooks/use-settings'
import {
  accountRoleText,
  connectMailAccount,
  INBOX_CATEGORY_OPTIONS,
  removeGoogleAccount,
  useGoogleAccounts,
  type GoogleAccount,
  type InboxCategories,
} from '@/shared/api/google-accounts-api'
import { queryKeys } from '@/shared/constants/query-keys'
import { Button } from '@/shared/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { cn } from '@/shared/utils/cn'

// Tài khoản Gmail (QĐ-50) trong màn Kết nối Google: danh sách tài khoản, thêm tài khoản chỉ Gmail (luồng OAuth role
// mail), gỡ tài khoản thêm; chọn loại thư vào Hộp tin.
export function GmailAccountsSection() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const accounts = useGoogleAccounts()
  const settings = useSettings()
  const patch = usePatchSettings()
  const [removing, setRemoving] = useState<GoogleAccount | null>(null)
  const categories = (settings.data?.['gmail.categories'] as InboxCategories | undefined) ?? 'primary_updates'

  const add = useMutation({
    mutationFn: connectMailAccount,
    onSuccess: async ({ auth_url }) => {
      if (isNative) await Browser.open({ url: auth_url })
      else if (auth_url.startsWith('/')) navigate(auth_url)
      else window.location.assign(auth_url)
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  const remove = useMutation({
    mutationFn: ({ id, deleteMessages }: { id: number; deleteMessages: boolean }) => removeGoogleAccount(id, deleteMessages),
    onSuccess: () => {
      setRemoving(null)
      toast.success('Đã gỡ tài khoản Gmail')
      void queryClient.invalidateQueries({ queryKey: queryKeys.google.accounts })
      void queryClient.invalidateQueries({ queryKey: ['inbox'] })
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  return (
    <section className="flex flex-col gap-3 rounded-2xl border bg-card p-4">
      <h2 className="font-semibold">Tài khoản Gmail</h2>
      <ul className="divide-y">
        {(accounts.data ?? []).map((account) => (
          <li key={account.id} className="flex items-center gap-3 py-2.5 text-sm">
            {account.status === 'active' ? <CircleCheck className="size-4 shrink-0 text-primary" /> : <TriangleAlert className="size-4 shrink-0 text-warning" />}
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{account.email}</span>
              <span className={cn('block text-xs', account.status === 'active' ? 'text-muted-foreground' : 'text-warning')}>
                {account.status === 'active' ? accountRoleText(account) : account.last_error || 'Cần kết nối lại'}
              </span>
            </span>
            {account.role === 'mail' && (
              <Button size="sm" variant="ghost" className="text-destructive" disabled={remove.isPending} onClick={() => setRemoving(account)}>
                Gỡ
              </Button>
            )}
          </li>
        ))}
      </ul>
      {accounts.isPending && <Loader2 className="size-4 animate-spin text-muted-foreground" />}
      <Button variant="outline" disabled={add.isPending} onClick={() => add.mutate()}>
        {add.isPending ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
        Thêm tài khoản Gmail
      </Button>
      <p className="text-xs text-muted-foreground">Tài khoản thêm chỉ dùng Gmail: thư vào Hộp tin, soạn và gửi qua thẻ duyệt. Lịch, Việc vẫn theo tài khoản chính.</p>

      <div className="flex flex-col gap-2 border-t pt-3">
        <p className="flex items-center gap-2 text-sm font-medium">
          <Mail className="size-4 text-muted-foreground" />
          Thư vào Hộp tin
        </p>
        <div className="flex flex-col gap-1.5" role="radiogroup" aria-label="Thư vào Hộp tin">
          {INBOX_CATEGORY_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={categories === option.value}
              disabled={patch.isPending}
              onClick={() => patch.mutate({ 'gmail.categories': option.value })}
              className={cn('flex items-start gap-3 rounded-xl border px-3 py-2 text-left text-sm', categories === option.value && 'border-primary bg-primary/5')}
            >
              <span className={cn('mt-0.5 size-4 shrink-0 rounded-full border-2', categories === option.value ? 'border-primary bg-primary' : 'border-muted-foreground/40')} />
              <span>
                <span className="block font-medium">{option.label}</span>
                <span className="block text-xs text-muted-foreground">{option.text}</span>
              </span>
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">Thư Google đánh dấu quan trọng luôn vào Hộp tin. Đổi lựa chọn thì lần đồng bộ sau lấy lại thư 7 ngày gần nhất.</p>
      </div>

      <Dialog open={!!removing} onOpenChange={(open) => !open && setRemoving(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="break-all">Gỡ {removing?.email}?</DialogTitle>
            <DialogDescription>App thôi đọc thư của tài khoản này. Hộp thư Gmail không bị đụng tới.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Button variant="destructive" disabled={remove.isPending} onClick={() => removing && remove.mutate({ id: removing.id, deleteMessages: true })}>
              {remove.isPending && <Loader2 className="size-4 animate-spin" />}
              Gỡ và bỏ thư của tài khoản khỏi Hộp tin
            </Button>
            <Button variant="outline" disabled={remove.isPending} onClick={() => removing && remove.mutate({ id: removing.id, deleteMessages: false })}>
              Gỡ, giữ thư đã lấy về
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  )
}
