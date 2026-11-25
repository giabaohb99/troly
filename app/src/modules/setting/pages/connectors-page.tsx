import { useEffect, useState } from 'react'
import { Browser } from '@capacitor/browser'
import { ChevronRight, CircleCheck, Loader2, Plug, Plus, TriangleAlert } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { isNative } from '@/core/config'
import { SubPage } from '@/modules/setting/components/sub-page'
import {
  addConnector,
  CONNECTORS_KEY,
  connectErrorText,
  connectorStatusText,
  FALLBACK_PRESETS,
  listPresets,
  nameFromUrl,
  useConnectors,
  validConnectorUrl,
  type Connector,
} from '@/shared/api/connectors-api'
import { EmptyState } from '@/shared/components/empty-state'
import { ErrorState } from '@/shared/components/error-state'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { useConnectFlow } from '@/shared/hooks/use-connect-flow'
import { Button } from '@/shared/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { cn } from '@/shared/utils/cn'

// Cài đặt → Kết nối (QĐ-56, như Claude): danh sách kết nối (tên, trạng thái, tài khoản); Thêm kết nối bằng tên và địa
// chỉ MCP (gợi ý sẵn ERP DEGO). Về từ trang đăng nhập: ?ok=1&id= hoặc ?ok=0&loi=.
export function ConnectorsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const prefill = (useLocation().state as { add?: { name?: string; url?: string } } | null)?.add
  const connectors = useConnectors()
  const [adding, setAdding] = useState(!!prefill)

  useEffect(() => {
    const ok = params.get('ok')
    if (ok === null) return
    if (ok === '1') toast.success('Đã nối.')
    else toast.error(connectErrorText(params.get('loi')))
    if (isNative) void Browser.close().catch(() => undefined)
    void queryClient.invalidateQueries({ queryKey: CONNECTORS_KEY })
    const id = params.get('id')
    setParams({}, { replace: true })
    if (ok === '1' && id) navigate(`/cai-dat/ket-noi/${id}`)
  }, [params, queryClient, setParams, navigate])

  return (
    <SubPage title="Kết nối" subtitle="Hệ thống ngoài trợ lý đọc được qua MCP">
      {connectors.isPending && <SkeletonList />}
      {connectors.isError && <ErrorState error={connectors.error} onRetry={() => void connectors.refetch()} />}
      {connectors.data && connectors.data.length === 0 && <EmptyState icon={Plug} text="Chưa có kết nối nào. Thêm ERP DEGO hoặc hệ thống khác có MCP." />}
      {connectors.data && connectors.data.length > 0 && (
        <ul className="divide-y rounded-2xl border bg-card">
          {connectors.data.map((c) => (
            <ConnectorRow key={c.id} item={c} onOpen={() => navigate(`/cai-dat/ket-noi/${c.id}`)} />
          ))}
        </ul>
      )}
      <Button onClick={() => setAdding(true)}>
        <Plus className="size-4" />
        Thêm kết nối
      </Button>
      <p className="px-1 text-xs text-muted-foreground">
        Bấm Kết nối thì trang đăng nhập của hệ thống mở trong app; nhập mật khẩu và đồng ý trên trang đó, xong tự quay lại. App không thấy mật khẩu. Công cụ ghi (tạo, sửa) mặc định tắt.
      </p>
      <AddConnectorDialog open={adding} onOpenChange={setAdding} prefill={prefill} />
    </SubPage>
  )
}

function ConnectorRow({ item, onOpen }: { item: Connector; onOpen: () => void }) {
  const connected = item.status === 'connected'
  const warn = item.status === 'reauth_required' || item.status === 'error'
  return (
    <li>
      <button type="button" onClick={onOpen} className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm">
        <Plug className="size-5 shrink-0 text-primary" />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{item.name}</span>
          <span className={cn('flex items-center gap-1 text-xs', connected ? 'text-primary' : warn ? 'text-warning' : 'text-muted-foreground')}>
            {connected && <CircleCheck className="size-3.5 shrink-0" />}
            {warn && <TriangleAlert className="size-3.5 shrink-0" />}
            <span className="truncate">{connectorStatusText(item)}</span>
          </span>
        </span>
        <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
      </button>
    </li>
  )
}

// Form thêm: tên + địa chỉ MCP, chip gợi ý. Thêm xong: OAuth thì mở trang đăng nhập ngay; cần khóa thì sang màn kết
// nối để dán khóa.
function AddConnectorDialog({ open, onOpenChange, prefill }: { open: boolean; onOpenChange: (open: boolean) => void; prefill?: { name?: string; url?: string } }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const connect = useConnectFlow()
  const [name, setName] = useState(prefill?.name ?? '')
  const [url, setUrl] = useState(prefill?.url ?? '')
  const presets = useQuery({ queryKey: ['connectors', 'presets'], queryFn: listPresets, enabled: open, retry: 0, staleTime: Infinity })
  const presetList = presets.data?.length ? presets.data : FALLBACK_PRESETS
  const problem = validConnectorUrl(url)

  const add = useMutation({
    mutationFn: () => addConnector({ name: name.trim() || nameFromUrl(url), url: url.trim() }),
    onSuccess: ({ connector, next }) => {
      void queryClient.invalidateQueries({ queryKey: CONNECTORS_KEY })
      onOpenChange(false)
      setName('')
      setUrl('')
      if (next === 'oauth') connect.mutate(connector.id)
      else navigate(`/cai-dat/ket-noi/${connector.id}`, { state: { askKey: next === 'api_key' } })
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Thêm kết nối</DialogTitle>
          <DialogDescription>Địa chỉ MCP của hệ thống, ví dụ ERP DEGO.</DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            if (!problem) add.mutate()
          }}
        >
          <div className="flex flex-wrap gap-1.5">
            {presetList.map((p) => (
              <button
                key={p.url}
                type="button"
                onClick={() => {
                  setName(p.name)
                  setUrl(p.url)
                }}
                className={cn('rounded-full border px-3 py-1 text-xs', url === p.url && 'border-primary bg-primary/15 text-primary')}
              >
                {p.name}
              </button>
            ))}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="conn-name">Tên</Label>
            <Input id="conn-name" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder={nameFromUrl(url) || 'ERP DEGO'} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="conn-url">Địa chỉ MCP</Label>
            <Input id="conn-url" type="url" inputMode="url" autoCapitalize="off" autoCorrect="off" spellCheck={false} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." />
            {url && problem && <p className="text-xs text-destructive">{problem}</p>}
          </div>
          <Button type="submit" disabled={!!problem || add.isPending || connect.isPending}>
            {(add.isPending || connect.isPending) && <Loader2 className="size-4 animate-spin" />}
            Kết nối
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
