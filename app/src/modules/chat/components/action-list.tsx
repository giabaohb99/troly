import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Brain, ChevronRight, CircleCheck, ExternalLink, FileText, Mail, Map, MapPin, Navigation, Sheet, Undo2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { Alarm } from '@/core/native/alarm'
import { Maps, placeUrl } from '@/core/native/maps'
import { openExternal } from '@/core/native/open-external'
import { restoreProfileRevision, restoreResources } from '@/modules/chat/api/chat-api'
import { ConfirmCard } from '@/shared/components/confirm-card'
import { KNOWN_ACTION_TYPES, type ChatAction, type PendingAction } from '@/modules/chat/types/chat'
import { screenToRoute } from '@/shared/utils/screen-route'
import { queryKeys } from '@/shared/constants/query-keys'
import { Button } from '@/shared/ui/button'
import { FileCard } from '@/modules/chat/components/file-card'

interface ActionListProps {
  actions: ChatAction[]
  pendingActions?: PendingAction[]
  onChoice?: (value: string) => void
  // Dòng xác nhận (open_screen ngay sau công cụ ghi dữ liệu) hiện như dòng nhỏ có dấu tích.
  disabled?: boolean
  // Tệp đã hiện bằng attachments của tin: bỏ hành động file trùng để không vẽ thẻ hai lần (QĐ-41).
  hiddenFileIds?: number[]
}

const LINK_ICONS = { file: FileText, gmail: Mail, sheet: Sheet, web: ExternalLink }

async function openOrWarn(url: string) {
  if (!(await openExternal(url))) toast.error('Link không an toàn, không mở.')
}

// Link bản đồ mở bằng app Google Maps nếu có (30 mục 3.12).
async function openMap(open: () => Promise<unknown>) {
  try {
    await open()
  } catch {
    toast.error('Không mở được bản đồ.')
  }
}

function UndoLine({ action }: { action: Extract<ChatAction, { type: 'undo' }> }) {
  const queryClient = useQueryClient()
  const [state, setState] = useState<'idle' | 'busy' | 'done'>('idle')
  const busyRef = useRef(false)
  const [expired] = useState(() => Date.parse(action.expires_at) < Date.now())

  async function undo() {
    if (busyRef.current) return
    busyRef.current = true
    setState('busy')
    try {
      await restoreResources(action)
      setState('done')
      void queryClient.invalidateQueries({ queryKey: queryKeys.expense.all })
      if (action.resource !== 'expense') {
        void queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all })
        void Alarm.sync()
      }
      toast.success('Đã hoàn tác')
    } catch (error) {
      setState('idle')
      toast.error(getErrorMessage(error))
    } finally {
      busyRef.current = false
    }
  }

  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <CircleCheck className="size-4 text-primary" />
      <span className="min-w-0">{state === 'done' ? 'Đã hoàn tác' : action.text}</span>
      {state !== 'done' && !expired && (
        <button type="button" disabled={state === 'busy'} onClick={() => void undo()} className="inline-flex items-center gap-1 font-medium text-primary">
          <Undo2 className="size-3.5" />
          {action.label || 'Hoàn tác'}
        </button>
      )}
    </p>
  )
}

function MemoryLine({ action }: { action: Extract<ChatAction, { type: 'memory_changed' }> }) {
  const queryClient = useQueryClient()
  const [undone, setUndone] = useState(false)
  const busyRef = useRef(false)

  async function undo() {
    if (busyRef.current) return
    busyRef.current = true
    try {
      await restoreProfileRevision(action.undo_version, action.version)
      setUndone(true)
      void queryClient.invalidateQueries({ queryKey: queryKeys.memory.profile })
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      busyRef.current = false
    }
  }

  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Brain className="size-4 shrink-0 text-primary" />
      <span className="min-w-0">{undone ? 'Đã hoàn tác ghi nhớ' : `Đã ghi nhớ: ${action.text}`}</span>
      {!undone && (
        <button type="button" onClick={() => void undo()} className="font-medium text-primary">
          Hoàn tác
        </button>
      )}
    </p>
  )
}

// Hiện hành động trợ lý trả về (31 mục 3.3). Kiểu lạ bỏ qua, không làm vỡ màn.
export function ActionList({ actions, pendingActions, onChoice, disabled, hiddenFileIds }: ActionListProps) {
  const navigate = useNavigate()
  const visible = actions.filter((action) => KNOWN_ACTION_TYPES.has(action.type) && !(action.type === 'file' && hiddenFileIds?.includes(action.file_id)))
  if (visible.length === 0) return null

  return (
    <div className="flex w-full flex-col items-start gap-2">
      {visible.map((action) => {
        switch (action.type) {
          case 'open_screen':
            return (
              <button
                key={action.id}
                type="button"
                onClick={() => navigate(screenToRoute(action.screen, action.params))}
                className="inline-flex items-center gap-1.5 text-sm font-medium text-primary"
              >
                <CircleCheck className="size-4" />
                {action.label}
                <ChevronRight className="size-4" />
              </button>
            )
          case 'open_link': {
            const Icon = LINK_ICONS[action.kind] ?? ExternalLink
            return (
              <Button key={action.id} variant="outline" size="sm" onClick={() => void openOrWarn(action.url)}>
                <Icon className="size-4" />
                {action.label}
              </Button>
            )
          }
          case 'open_map_navigation':
            return (
              <Button key={action.id} variant="outline" className="w-full justify-start" onClick={() => void openMap(() => Maps.navigate({ lat: action.lat, lng: action.lng, query: action.query, mode: action.mode, avoid: action.avoid, uri: action.uri, fallbackUrl: action.fallback_url }))}>
                <Navigation className="size-4" />
                {action.label}
              </Button>
            )
          case 'open_map_directions':
            return action.urls.map((url, index) => (
              <Button key={`${action.id}-${index}`} variant="outline" className="w-full justify-start" onClick={() => void openMap(() => Maps.openUrl({ url }))}>
                <Map className="size-4" />
                {action.segment_labels[index] ?? action.label}
              </Button>
            ))
          case 'open_map_place':
            return (
              <Button
                key={action.id}
                variant="outline"
                size="sm"
                onClick={() => void openMap(() => Maps.openUrl({ url: placeUrl(action.query, action.place_id) }))}
              >
                <MapPin className="size-4" />
                {action.label}
              </Button>
            )
          case 'file':
            return <FileCard key={action.id} file={action} />
          case 'undo':
            return <UndoLine key={action.id} action={action} />
          case 'memory_changed':
            return <MemoryLine key={action.id} action={action} />
          case 'confirm':
            return (
              <ConfirmCard
                key={action.id}
                action={action}
                serverStatus={pendingActions?.find((p) => p.id === action.pending_action_id)?.status}
                lookupStatus={!!pendingActions && !pendingActions.some((p) => p.id === action.pending_action_id)}
              />
            )
          case 'choices':
            return (
              <div key={action.id} className="flex flex-wrap gap-2">
                {action.options.map((option) => (
                  <Button key={option.value} variant="secondary" size="sm" disabled={disabled || !onChoice} onClick={() => onChoice?.(option.value)}>
                    {option.label}
                  </Button>
                ))}
              </div>
            )
          default:
            return null
        }
      })}
    </div>
  )
}
