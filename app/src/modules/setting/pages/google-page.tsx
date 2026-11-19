import { useEffect, useState } from 'react'
import { Browser } from '@capacitor/browser'
import { ArrowLeft, CalendarDays, CircleCheck, Cloud, ListTodo, Loader2, Mail, RefreshCw, TriangleAlert, Unplug } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { isNative } from '@/core/config'
import { connectGoogle, disconnectGoogle, listOutbox, retryOutbox, syncGoogle, type OutboxItem } from '@/modules/setting/api/google-api'
import { ErrorState } from '@/shared/components/error-state'
import { queryKeys } from '@/shared/constants/query-keys'
import { needsReconnect, useGoogleStatus, type GooglePack, type GooglePackName } from '@/shared/hooks/use-google-status'
import { Button } from '@/shared/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { Switch } from '@/shared/ui/switch'
import { formatDayTitle, formatTime, toDateKey } from '@/shared/utils/format'

// Gói dùng ở Phase 3; Gmail, Danh bạ, Drive bật ở phase sau (00 mục phase).
const PHASE3_PACKS: { name: GooglePackName; label: string; icon: typeof CalendarDays; text: string }[] = [
  { name: 'calendar', label: 'Lịch', icon: CalendarDays, text: 'Lịch hai chiều, Google làm gốc.' },
  { name: 'tasks', label: 'Việc', icon: ListTodo, text: 'Việc có ngày lên Google Tasks, tích xong ở đâu cũng được.' },
  // QĐ-43: đọc thư vào Hộp tin, trả lời và gửi thư mới qua thẻ duyệt.
  { name: 'gmail', label: 'Gmail', icon: Mail, text: 'Đọc thư vào Hộp tin; trả lời, gửi thư mới đều qua thẻ duyệt.' },
]

const RESULT_TEXT: Record<string, { ok: boolean; text: string }> = {
  ok: { ok: true, text: 'Đã kết nối Google. Đang lấy lịch và việc lần đầu.' },
  huy: { ok: false, text: 'Đã hủy, chưa kết nối Google.' },
  'thieu-quyen': { ok: false, text: 'Thiếu quyền: khi Google hỏi, tích đủ các ô rồi thử lại.' },
  loi: { ok: false, text: 'Kết nối Google bị lỗi, thử lại sau.' },
}

const OP_LABEL: Record<string, string> = { create: 'Tạo', insert: 'Tạo', update: 'Sửa', patch: 'Sửa', delete: 'Xóa', complete: 'Tích xong' }
const TYPE_LABEL: Record<string, string> = { event: 'sự kiện', task: 'việc', gmail_draft: 'thư nháp', file: 'tệp', export: 'bảng xuất' }

function when(iso: string | null): string {
  if (!iso) return 'chưa đồng bộ'
  const key = toDateKey(iso)
  return key === toDateKey(new Date()) ? `đồng bộ ${formatTime(iso)}` : `đồng bộ ${formatDayTitle(key).split(', ')[1]} ${formatTime(iso)}`
}

// Màn Kết nối Google (31 mục 3.5 Cài đặt). Mở trang đồng ý bằng Custom Tab; máy chủ đưa về troly://cai-dat/google?ket-qua=.
export function GooglePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const status = useGoogleStatus()
  const outbox = useQuery({ queryKey: queryKeys.google.outbox, queryFn: listOutbox, enabled: !!status.data?.connected, select: (data) => data.items })
  const [packs, setPacks] = useState<GooglePackName[]>(['calendar', 'tasks'])
  const [disconnectOpen, setDisconnectOpen] = useState(false)
  const result = params.get('ket-qua')

  const refreshAll = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.google.status })
    void queryClient.invalidateQueries({ queryKey: queryKeys.google.outbox })
    void queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all })
  }

  // Về từ trang kết nối: đóng Custom Tab, báo kết quả, tải lại trạng thái.
  useEffect(() => {
    if (!result) return
    const info = RESULT_TEXT[result] ?? RESULT_TEXT.loi
    if (info.ok) toast.success(info.text)
    else toast.error(info.text)
    if (isNative) void Browser.close().catch(() => undefined)
    void queryClient.invalidateQueries({ queryKey: queryKeys.google.status })
    void queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all })
    setParams({}, { replace: true })
  }, [result, queryClient, setParams])

  const connect = useMutation({
    mutationFn: (wanted: GooglePackName[]) => connectGoogle(wanted),
    onSuccess: async ({ auth_url }) => {
      if (isNative) await Browser.open({ url: auth_url })
      else if (auth_url.startsWith('/')) navigate(auth_url)
      else window.location.assign(auth_url)
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const sync = useMutation({
    mutationFn: (service: string) => syncGoogle(service),
    onSuccess: () => {
      toast.success('Đã đặt đồng bộ')
      setTimeout(refreshAll, 2_500)
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const disconnect = useMutation({
    mutationFn: (keepData: boolean) => disconnectGoogle(keepData),
    onSuccess: () => {
      setDisconnectOpen(false)
      toast.success('Đã ngắt kết nối Google')
      refreshAll()
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const data = status.data
  const enabledPacks = (data?.packs ?? []).filter((p) => p.enabled).map((p) => p.name)

  return (
    <div className="flex flex-col gap-4 pb-8">
      <div className="flex items-center gap-2">
        <Button size="icon" variant="ghost" aria-label="Quay lại" onClick={() => navigate('/cai-dat')}>
          <ArrowLeft className="size-5" />
        </Button>
        <h1 className="text-2xl font-bold">Kết nối Google</h1>
      </div>

      {status.isPending && (
        <div className="flex justify-center py-10 text-muted-foreground">
          <Loader2 className="size-6 animate-spin" />
        </div>
      )}
      {status.isError && <ErrorState error={status.error} onRetry={() => void status.refetch()} />}

      {data && !data.connected && (
        <section className="flex flex-col gap-4 rounded-2xl border bg-card p-4">
          <p className="flex items-center gap-2 font-semibold">
            <Cloud className="size-5 text-primary" />
            Chưa kết nối
          </p>
          <p className="text-sm text-muted-foreground">
            Google mở trong một thẻ trình duyệt. Màn <em>Google chưa xác minh ứng dụng này</em> hiện ra thì bấm <em>Nâng cao</em> rồi <em>Đi tới</em>, sau đó tích đủ các ô quyền.
          </p>
          <div className="flex flex-col gap-3">
            {PHASE3_PACKS.map((pack) => (
              <label key={pack.name} className="flex items-start gap-3 text-sm">
                <pack.icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{pack.label}</span>
                  <span className="block text-muted-foreground">{pack.text}</span>
                </span>
                <Switch
                  checked={packs.includes(pack.name)}
                  aria-label={`Gói ${pack.label}`}
                  onCheckedChange={(on) => setPacks(on ? [...packs, pack.name] : packs.filter((p) => p !== pack.name))}
                />
              </label>
            ))}
          </div>
          <Button disabled={connect.isPending || packs.length === 0} onClick={() => connect.mutate(packs)}>
            {connect.isPending && <Loader2 className="size-4 animate-spin" />}
            Kết nối Google
          </Button>
        </section>
      )}

      {data?.connected && (
        <>
          <section className="flex flex-col gap-2 rounded-2xl border bg-card p-4">
            <p className="flex items-center gap-2 font-semibold">
              {needsReconnect(data) ? <TriangleAlert className="size-5 text-warning" /> : <CircleCheck className="size-5 text-primary" />}
              {data.email}
            </p>
            {needsReconnect(data) ? (
              <div className="flex flex-col gap-2 text-sm">
                <p className="text-warning">Google đã thu hồi quyền hoặc mã hết hạn. Cần kết nối lại.</p>
                <Button disabled={connect.isPending} onClick={() => connect.mutate(enabledPacks.length ? enabledPacks : packs)}>
                  {connect.isPending && <Loader2 className="size-4 animate-spin" />}
                  Kết nối lại
                </Button>
              </div>
            ) : (
              data.initial_sync.message && <p className="text-sm text-muted-foreground">{data.initial_sync.message}</p>
            )}
          </section>

          <section className="rounded-2xl border bg-card p-4">
            <h2 className="mb-2 font-semibold">Dịch vụ</h2>
            <ul className="divide-y">
              {PHASE3_PACKS.map((meta) => {
                const pack: GooglePack | undefined = data.packs.find((p) => p.name === meta.name)
                return (
                  <li key={meta.name} className="flex items-center gap-3 py-2.5 text-sm">
                    <meta.icon className="size-4 shrink-0 text-muted-foreground" />
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium">{meta.label}</span>
                      <span className={pack?.status === 'error' ? 'block text-xs text-destructive' : 'block text-xs text-muted-foreground'}>
                        {!pack?.enabled ? 'Chưa bật' : !pack.granted ? 'Thiếu quyền' : pack.status === 'error' ? pack.last_error || 'Lỗi đồng bộ' : when(pack.last_sync_at)}
                      </span>
                    </span>
                    {pack?.enabled && pack.granted ? (
                      <Button size="sm" variant="ghost" aria-label={`Đồng bộ ${meta.label}`} disabled={sync.isPending} onClick={() => sync.mutate(meta.name)}>
                        <RefreshCw className="size-4" />
                      </Button>
                    ) : (
                      <Button size="sm" variant="secondary" disabled={connect.isPending} onClick={() => connect.mutate([...enabledPacks, meta.name])}>
                        {meta.name === 'gmail' ? 'Cấp quyền Gmail' : 'Bật'}
                      </Button>
                    )}
                  </li>
                )
              })}
            </ul>
          </section>

          {(outbox.data?.length ?? 0) > 0 && (
            <section className="rounded-2xl border border-warning/40 bg-warning/5 p-4">
              <h2 className="mb-2 font-semibold text-warning">Lỗi đồng bộ ({outbox.data?.length})</h2>
              <ul className="divide-y">
                {outbox.data?.map((item) => (
                  <OutboxRow key={item.id} item={item} onDone={refreshAll} />
                ))}
              </ul>
            </section>
          )}

          <Button variant="outline" onClick={() => setDisconnectOpen(true)}>
            <Unplug className="size-4" />
            Ngắt kết nối
          </Button>
        </>
      )}

      <Dialog open={disconnectOpen} onOpenChange={setDisconnectOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ngắt kết nối Google?</DialogTitle>
            <DialogDescription>Lịch và việc trên Google không bị đụng tới. Chọn có giữ bản đã lấy về app không.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Button disabled={disconnect.isPending} onClick={() => disconnect.mutate(true)}>
              {disconnect.isPending && <Loader2 className="size-4 animate-spin" />}
              Ngắt, giữ dữ liệu trên app
            </Button>
            <Button variant="destructive" disabled={disconnect.isPending} onClick={() => disconnect.mutate(false)}>
              Ngắt và xóa dữ liệu Google trên app
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function OutboxRow({ item, onDone }: { item: OutboxItem; onDone: () => void }) {
  const retry = useMutation({
    mutationFn: (reapply: boolean) => retryOutbox(item.id, reapply),
    onSuccess: () => {
      toast.success('Đã đặt thử lại')
      onDone()
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  const label = `${OP_LABEL[item.op] ?? item.op} ${TYPE_LABEL[item.local_type] ?? item.local_type}`
  return (
    <li className="flex flex-col gap-2 py-2.5 text-sm">
      <span>
        <span className="font-medium">{label}</span>
        <span className="block text-xs text-muted-foreground">
          {item.status === 'conflict' ? 'Google vừa có bản khác; thay đổi của app chưa áp.' : item.last_error || 'Lỗi chưa rõ'} · thử {item.attempts} lần
        </span>
      </span>
      <div className="flex gap-2">
        <Button size="sm" variant="secondary" disabled={retry.isPending} onClick={() => retry.mutate(false)}>
          Thử lại
        </Button>
        {item.status === 'conflict' && (
          <Button size="sm" disabled={retry.isPending} onClick={() => retry.mutate(true)}>
            Áp lại
          </Button>
        )}
      </div>
    </li>
  )
}
