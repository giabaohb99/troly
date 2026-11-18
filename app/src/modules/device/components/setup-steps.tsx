import { useState, type ReactNode } from 'react'
import { ChevronDown, Circle, CircleCheck } from 'lucide-react'
import { toast } from 'sonner'
import { System, type PermissionSnapshot, type SettingsTarget } from '@/core/native/system'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/utils/cn'

export const SAMSUNG_DONE_KEY = 'troly.setup.samsung-never-sleeping'
const SAMSUNG_PATH = 'Cài đặt > Pin và chăm sóc thiết bị > Pin > Giới hạn sử dụng nền > Ứng dụng không bao giờ ngủ > dấu cộng > Trợ lý > Thêm'

function Step({ done, index, title, reason, children }: { done: boolean; index: number; title: string; reason: string; children?: ReactNode }) {
  return (
    <li className="flex gap-3 py-3">
      {done ? <CircleCheck className="mt-0.5 size-5 shrink-0 text-primary" /> : <Circle className="mt-0.5 size-5 shrink-0 text-muted-foreground" />}
      <div className="min-w-0 flex-1">
        <p className={cn('font-medium', done && 'text-muted-foreground')}>
          {index}. {title}
        </p>
        <p className="text-sm text-muted-foreground">{reason}</p>
        {!done && children && <div className="mt-2 flex flex-wrap gap-2">{children}</div>}
      </div>
    </li>
  )
}

async function open(target: SettingsTarget) {
  const { opened } = await System.openSettings({ target })
  if (!opened) toast.error('Máy không mở được trang này, làm theo hướng dẫn bên dưới.')
  return opened
}

// Các bước cấp quyền (31 luồng 2, 30 mục 3.10). Mỗi bước một nút mở đúng trang; quay lại app thì tự kiểm lại.
export function SetupSteps({ permissions }: { permissions: PermissionSnapshot }) {
  const [restrictedOpen, setRestrictedOpen] = useState(false)
  const [samsungDone, setSamsungDone] = useState(() => localStorage.getItem(SAMSUNG_DONE_KEY) === '1')
  const [samsungManual, setSamsungManual] = useState(false)
  const isSamsung = permissions.manufacturer.toLowerCase() === 'samsung'
  let index = 0

  return (
    <ol className="divide-y">
      <Step done={permissions.notifications} index={++index} title="Cho phép thông báo" reason="Để nhắc lịch, báo bản mới.">
        <Button size="sm" onClick={() => void System.requestNotifications()}>
          Bật
        </Button>
      </Step>

      <Step done={permissions.notificationListener} index={++index} title="Đọc thông báo" reason="Để gom tin Zalo, Telegram, SMS và tự ghi chi tiêu từ ngân hàng. Tin có mã OTP luôn bị bỏ trên máy.">
        <Button size="sm" onClick={() => void open('notification_listener')}>
          Bật
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setRestrictedOpen((v) => !v)}>
          Bị khóa xám?
          <ChevronDown className={cn('size-4 transition-transform', restrictedOpen && 'rotate-180')} />
        </Button>
        {restrictedOpen && (
          <div className="w-full rounded-xl bg-secondary p-3 text-sm">
            <p className="mb-2 text-muted-foreground">App cài ngoài cửa hàng nên Android khóa quyền này tới khi cho phép cài đặt bị hạn chế:</p>
            <ol className="list-decimal space-y-1 pl-5">
              <li>Bấm Bật ở trên một lần, thấy công tắc bị khóa thì quay lại đây.</li>
              <li>Bấm Mở thông tin ứng dụng bên dưới.</li>
              <li>Bấm menu ba chấm góc trên, chọn Cho phép cài đặt bị hạn chế, xác nhận.</li>
              <li>Quay lại, bấm Bật ở bước này lần nữa.</li>
            </ol>
            <Button size="sm" variant="secondary" className="mt-3" onClick={() => void open('app_details')}>
              Mở thông tin ứng dụng
            </Button>
          </div>
        )}
      </Step>

      <Step done={permissions.batteryUnrestricted} index={++index} title="Pin không hạn chế" reason="Để Android không tắt trợ lý khi chạy nền.">
        <Button size="sm" onClick={() => void open('battery')}>
          Bật
        </Button>
      </Step>

      {isSamsung && (
        <Step done={samsungDone} index={++index} title="Không cho ngủ (Samsung)" reason="Samsung tự cho app ngủ sau vài ngày không mở; khi đó nhắc lịch và tin mới có thể không tới.">
          <Button
            size="sm"
            onClick={() =>
              void open('samsung_never_sleeping').then((opened) => {
                if (!opened) setSamsungManual(true)
              })
            }
          >
            Mở danh sách
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              localStorage.setItem(SAMSUNG_DONE_KEY, '1')
              setSamsungDone(true)
            }}
          >
            Đã làm
          </Button>
          <button type="button" className="text-sm text-primary" onClick={() => setSamsungManual((v) => !v)}>
            Làm tay
          </button>
          {samsungManual && <p className="w-full rounded-xl bg-secondary p-3 text-sm">{SAMSUNG_PATH}</p>}
        </Step>
      )}

      {!permissions.exactAlarm && (
        <Step done={false} index={++index} title="Báo thức chính xác" reason="Để nhắc kêu đúng giờ.">
          <Button size="sm" onClick={() => void open('exact_alarm')}>
            Bật
          </Button>
        </Step>
      )}
    </ol>
  )
}
