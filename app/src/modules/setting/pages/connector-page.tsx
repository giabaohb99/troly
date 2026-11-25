import { useState } from 'react'
import { ChevronLeft, CircleCheck, KeyRound, Loader2, PenLine, RefreshCw, Trash2, TriangleAlert, Wrench } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { SettingSection } from '@/modules/setting/components/sub-page'
import { CONNECTORS_KEY, connectorStatusText, listConnectorTools, removeConnector, saveConnectorKey, toggledWriteTools, updateConnector, useConnectors, type ConnectorTool } from '@/shared/api/connectors-api'
import { ErrorState } from '@/shared/components/error-state'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { useConnectFlow } from '@/shared/hooks/use-connect-flow'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/confirm-dialog'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { Switch } from '@/shared/ui/switch'
import { cn } from '@/shared/utils/cn'

// Một kết nối (QĐ-56): trạng thái, Kết nối hoặc Nối lại (OAuth) hoặc dán khóa (che), danh sách công cụ, công tắc công cụ
// ghi bật từng cái theo tên (mặc định tắt, bật có cảnh báo), Gỡ.
export function ConnectorPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const id = Number(useParams().connectorId)
  const askKey = !!(useLocation().state as { askKey?: boolean } | null)?.askKey
  const connectors = useConnectors()
  const item = connectors.data?.find((c) => c.id === id) ?? null
  const connected = item?.status === 'connected'
  const tools = useQuery({ queryKey: ['connectors', id, 'tools'], queryFn: () => listConnectorTools(id), enabled: connected, select: (d) => d.items })
  const connect = useConnectFlow()
  const [keyOpen, setKeyOpen] = useState(askKey)
  const [confirmTool, setConfirmTool] = useState<ConnectorTool | null>(null)
  const refresh = () => void queryClient.invalidateQueries({ queryKey: CONNECTORS_KEY })

  // Bật, tắt một công cụ ghi: gửi lại cả danh sách công cụ ghi đang bật (dạng đã chốt với agent Google).
  const toggleWrite = useMutation({
    mutationFn: ({ tool, on }: { tool: ConnectorTool; on: boolean }) => {
      const current = tools.data?.filter((t) => t.write && t.enabled).map((t) => t.name) ?? item?.write_tools_enabled ?? []
      return updateConnector(id, { write_tools_enabled: toggledWriteTools(current, tool.name, on) })
    },
    onSuccess: (_c, { tool, on }) => {
      refresh()
      void queryClient.invalidateQueries({ queryKey: ['connectors', id, 'tools'] })
      toast.success(`${on ? 'Đã bật' : 'Đã tắt'} ${tool.title || tool.name}`)
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  const remove = useMutation({
    mutationFn: () => removeConnector(id),
    onSuccess: () => {
      refresh()
      toast.success('Đã gỡ kết nối')
      navigate('/cai-dat/ket-noi', { replace: true })
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  return (
    <div className="flex flex-col gap-4 pb-8">
      <div className="flex items-center gap-1">
        <Button size="icon" variant="ghost" aria-label="Quay lại" onClick={() => navigate('/cai-dat/ket-noi')}>
          <ChevronLeft className="size-5" />
        </Button>
        <div className="min-w-0">
          <h1 className="truncate text-xl font-bold">{item?.name ?? 'Kết nối'}</h1>
          {item && <p className="truncate text-xs text-muted-foreground">{item.url}</p>}
        </div>
      </div>
      {connectors.isPending && <SkeletonList />}
      {connectors.isError && <ErrorState error={connectors.error} onRetry={() => void connectors.refetch()} />}
      {connectors.isSuccess && !item && <p className="text-sm text-muted-foreground">Kết nối này không còn.</p>}

      {item && (
        <>
          <SettingSection title="Trạng thái">
            <p className={cn('flex items-center gap-1.5 text-sm', connected ? 'text-primary' : item.status === 'not_connected' ? 'text-muted-foreground' : 'text-warning')}>
              {connected ? <CircleCheck className="size-4" /> : item.status !== 'not_connected' && <TriangleAlert className="size-4" />}
              {connectorStatusText(item)}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {item.auth === 'oauth' && (
                <Button size="sm" variant={connected ? 'outline' : 'default'} disabled={connect.isPending} onClick={() => connect.mutate(item.id)}>
                  {connect.isPending ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                  {connected || item.status === 'reauth_required' ? 'Nối lại' : 'Kết nối'}
                </Button>
              )}
              {item.auth === 'api_key' && (
                <Button size="sm" variant={connected ? 'outline' : 'default'} onClick={() => setKeyOpen(true)}>
                  <KeyRound className="size-4" />
                  {connected ? 'Đổi khóa' : 'Nhập khóa'}
                </Button>
              )}
            </div>
          </SettingSection>

          <SettingSection title="Công cụ">
            {!connected && <p className="text-sm text-muted-foreground">Nối xong thì thấy danh sách công cụ.</p>}
            {connected && tools.isPending && <Loader2 className="size-4 animate-spin text-muted-foreground" />}
            {connected && tools.isError && <ErrorState error={tools.error} onRetry={() => void tools.refetch()} />}
            {tools.data && (
              <ul className="flex flex-col gap-2.5">
                {tools.data.map((t) => (
                  <li key={t.name} className="flex items-start gap-2 text-sm">
                    {t.write ? <PenLine className="mt-0.5 size-4 shrink-0 text-warning" /> : <Wrench className="mt-0.5 size-4 shrink-0 text-muted-foreground" />}
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium">{t.title || t.name}</span>
                      {t.title && <span className="block font-mono text-[11px] text-muted-foreground">{t.name}</span>}
                      {t.description && <span className="block text-xs text-muted-foreground">{t.description}</span>}
                    </span>
                    {t.write ? (
                      // Công cụ ghi: mỗi cái một công tắc, mặc định tắt; bật có cảnh báo.
                      <Switch
                        checked={t.enabled}
                        disabled={toggleWrite.isPending}
                        aria-label={`Cho dùng ${t.title || t.name}`}
                        onCheckedChange={(on) => (on ? setConfirmTool(t) : toggleWrite.mutate({ tool: t, on: false }))}
                      />
                    ) : (
                      <span className="shrink-0 rounded-full bg-muted px-1.5 text-[11px] text-muted-foreground">đọc</span>
                    )}
                  </li>
                ))}
                {tools.data.length === 0 && <li className="text-sm text-muted-foreground">Hệ thống chưa công bố công cụ nào.</li>}
              </ul>
            )}
            {tools.data?.some((t) => t.write) && <p className="mt-3 border-t pt-3 text-xs text-muted-foreground">Công cụ ghi (tạo, sửa dữ liệu) mặc định tắt. Bật cái nào thì trợ lý mới được dùng cái đó, và mỗi lần ghi vẫn hiện thẻ duyệt.</p>}
          </SettingSection>

          <ConfirmDialog
            title={`Gỡ kết nối ${item.name}?`}
            description="Trợ lý thôi đọc dữ liệu từ hệ thống này và đăng nhập bị thu hồi. Dữ liệu trên hệ thống không bị đụng tới."
            confirmLabel="Gỡ"
            onConfirm={() => remove.mutate()}
            trigger={
              <Button variant="outline" className="text-destructive">
                <Trash2 className="size-4" />
                Gỡ kết nối
              </Button>
            }
          />
          <ConfirmDialog
            open={!!confirmTool}
            onOpenChange={(open) => !open && setConfirmTool(null)}
            title={`Bật ${confirmTool?.title || confirmTool?.name || 'công cụ ghi'}?`}
            description={`Trợ lý sẽ được dùng công cụ này để tạo, sửa dữ liệu trên ${item.name}. Mỗi lần ghi vẫn hiện thẻ duyệt, nhưng hãy chỉ bật khi cần.`}
            confirmLabel="Bật"
            danger={false}
            onConfirm={() => confirmTool && toggleWrite.mutate({ tool: confirmTool, on: true })}
          />
          <KeyDialog connectorId={item.id} name={item.name} open={keyOpen} onOpenChange={setKeyOpen} onSaved={refresh} />
        </>
      )}
    </div>
  )
}

// Dán khóa cho máy chủ không có OAuth: ô che, không tự điền, không lưu trên máy.
function KeyDialog({ connectorId, name, open, onOpenChange, onSaved }: { connectorId: number; name: string; open: boolean; onOpenChange: (open: boolean) => void; onSaved: () => void }) {
  const [key, setKey] = useState('')
  const save = useMutation({
    mutationFn: () => saveConnectorKey(connectorId, key.trim()),
    onSuccess: () => {
      setKey('')
      onOpenChange(false)
      onSaved()
      toast.success('Đã lưu khóa')
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setKey('')
        onOpenChange(next)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Khóa cho {name}</DialogTitle>
          <DialogDescription>Hệ thống này không có trang đăng nhập; dán khóa API. Khóa được mã hóa trên máy chủ, không hiện lại.</DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            if (key.trim()) save.mutate()
          }}
        >
          <Input
            type="password"
            name="connector-secret-input"
            autoComplete="new-password"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            data-1p-ignore
            data-lpignore="true"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="Dán khóa vào đây"
            aria-label="Khóa"
          />
          <Button type="submit" disabled={!key.trim() || save.isPending}>
            {save.isPending && <Loader2 className="size-4 animate-spin" />}
            Lưu và thử
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
