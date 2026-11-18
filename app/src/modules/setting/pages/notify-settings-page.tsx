import { ChevronRight, Moon } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { isNative } from '@/core/config'
import { Alarm, NOTIFY_CHANNELS, type NotifyPrefs } from '@/core/native/alarm'
import type { SettingValues } from '@/modules/setting/api/setting-api'
import { SettingSection, SubPage } from '@/modules/setting/components/sub-page'
import { usePatchSettings, useSettings } from '@/modules/setting/hooks/use-settings'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { queryKeys } from '@/shared/constants/query-keys'
import { Input } from '@/shared/ui/input'
import { Switch } from '@/shared/ui/switch'
import { cn } from '@/shared/utils/cn'

const REMIND_OPTIONS = [0, 5, 10, 15, 30, 60]

function ToggleRow({ title, text, checked, disabled, onChange }: { title: string; text: string; checked: boolean; disabled?: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-start justify-between gap-3 py-2 text-sm">
      <span>
        <span className="block font-medium">{title}</span>
        <span className="block text-muted-foreground">{text}</span>
      </span>
      <Switch checked={checked} disabled={disabled} onCheckedChange={onChange} aria-label={title} />
    </label>
  )
}

// Cài đặt, Thông báo (QĐ-38): nhắc mặc định, kêu và rung, giờ yên lặng (lưu trên máy); loại thông báo (lưu máy
// chủ, máy chủ lọc /device/notices và /calendar/reminders); mỗi loại một kênh Android.
export function NotifySettingsPage() {
  const queryClient = useQueryClient()
  const settings = useSettings()
  const patch = usePatchSettings()
  const prefs = useQuery({ queryKey: queryKeys.device.notifyPrefs, queryFn: () => Alarm.getNotifyPrefs() })
  const savePrefs = useMutation({
    mutationFn: (change: Partial<NotifyPrefs>) => Alarm.setNotifyPrefs(change),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.device.notifyPrefs }),
    onError: () => toast.error('Không lưu được cài đặt trên máy.'),
  })
  const v = settings.data
  const p = prefs.data
  const remind = v?.['calendar.default_remind_minutes']?.[0] ?? null
  const quietOn = !!p?.quietStart && !!p?.quietEnd

  const saveServer = (values: Partial<SettingValues>, after?: () => void) =>
    patch.mutate(values, {
      onSuccess: () => {
        after?.()
      },
    })

  return (
    <SubPage title="Thông báo" subtitle="Nhắc, âm thanh, giờ yên lặng, loại thông báo">
      {(!v || !p) && <SkeletonList />}
      {v && p && (
        <>
          <SettingSection title="Nhắc lịch mặc định">
            <p className="mb-2 text-sm text-muted-foreground">Sự kiện tạo ở app được nhắc trước bao lâu.</p>
            <div className="flex flex-wrap gap-2">
              {REMIND_OPTIONS.map((minutes) => (
                <button
                  key={minutes}
                  type="button"
                  aria-pressed={remind === minutes}
                  disabled={patch.isPending}
                  onClick={() => saveServer({ 'calendar.default_remind_minutes': [minutes] })}
                  className={cn('rounded-full border px-3 py-1 text-sm', remind === minutes && 'border-primary bg-primary/15 text-primary')}
                >
                  {minutes === 0 ? 'Đúng giờ' : `${minutes} phút`}
                </button>
              ))}
            </div>
          </SettingSection>

          <SettingSection title="Âm thanh">
            <ToggleRow title="Kêu và rung" text="Nhắc là thông báo kêu một tiếng như tin nhắn. Tắt thì vẫn hiện nhưng im lặng; báo thức vẫn kêu." checked={p.sound} onChange={(on) => savePrefs.mutate({ sound: on })} />
            <ToggleRow
              title="Giờ yên lặng"
              text="Trong khung giờ này thông báo không kêu, trừ báo thức bạn bảo trợ lý đặt."
              checked={quietOn}
              onChange={(on) => savePrefs.mutate(on ? { quietStart: '22:00', quietEnd: '07:00' } : { quietStart: null, quietEnd: null })}
            />
            {quietOn && (
              <div className="mt-1 flex items-center gap-2 text-sm">
                <Moon className="size-4 shrink-0 text-muted-foreground" />
                <Input
                  aria-label="Giờ yên lặng bắt đầu"
                  type="time"
                  defaultValue={p.quietStart ?? ''}
                  onBlur={(e) => e.target.value && e.target.value !== p.quietStart && savePrefs.mutate({ quietStart: e.target.value })}
                />
                tới
                <Input
                  aria-label="Giờ yên lặng kết thúc"
                  type="time"
                  defaultValue={p.quietEnd ?? ''}
                  onBlur={(e) => e.target.value && e.target.value !== p.quietEnd && savePrefs.mutate({ quietEnd: e.target.value })}
                />
              </div>
            )}
            <p className="mt-2 text-xs text-muted-foreground">Lưu trên máy này.</p>
          </SettingSection>

          <SettingSection title="Loại thông báo">
            <ToggleRow
              title="Báo khi ghi giao dịch mới"
              text="Trợ lý ghi một khoản chi, thu từ thông báo ngân hàng thì báo một dòng."
              checked={v['notify.new_transaction'] ?? false}
              disabled={patch.isPending}
              onChange={(on) => saveServer({ 'notify.new_transaction': on })}
            />
            <ToggleRow
              title="Báo tin quan trọng"
              text="Tin của người quan trọng hoặc có từ khóa gấp."
              checked={v['notify.important_message'] ?? true}
              disabled={patch.isPending}
              onChange={(on) => saveServer({ 'notify.important_message': on })}
            />
            <ToggleRow
              title="Báo khi trợ lý trả lời"
              text="Gửi câu hỏi rồi rời app thì báo khi trợ lý trả lời xong; bấm mở đúng câu trả lời hoặc tệp."
              checked={(v['notify.chat_done'] ?? true) && p.chatDone}
              disabled={patch.isPending}
              onChange={(on) => {
                savePrefs.mutate({ chatDone: on })
                saveServer({ 'notify.chat_done': on })
              }}
            />
            <ToggleRow
              title="App nhắc cả sự kiện tạo trên Google"
              text="Bật thì app nhắc thay Google cho sự kiện tạo trên Google Calendar; nên tắt nhắc của Google để khỏi nhắc hai lần."
              checked={v['calendar.app_reminds_google'] ?? false}
              disabled={patch.isPending}
              onChange={(on) => saveServer({ 'calendar.app_reminds_google': on }, () => void Alarm.sync())}
            />
          </SettingSection>

          {isNative && (
            <SettingSection title="Kênh trên máy">
              <p className="mb-1 text-sm text-muted-foreground">Mỗi loại một kênh; chỉnh âm thanh, rung, cách hiện trong cài đặt của Android.</p>
              <ul className="divide-y">
                {NOTIFY_CHANNELS.map((channel) => (
                  <li key={channel.id}>
                    <button type="button" onClick={() => void Alarm.openChannelSettings({ channel: channel.id })} className="flex w-full items-center justify-between py-2.5 text-left text-sm">
                      {channel.label}
                      <ChevronRight className="size-4 text-muted-foreground" />
                    </button>
                  </li>
                ))}
              </ul>
            </SettingSection>
          )}
        </>
      )}
    </SubPage>
  )
}
