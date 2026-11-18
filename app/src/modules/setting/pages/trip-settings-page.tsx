import { useState } from 'react'
import { Loader2, Ship } from 'lucide-react'
import { toast } from 'sonner'
import type { Ferry, SettingValues } from '@/modules/setting/api/setting-api'
import { SettingSection, SubPage } from '@/modules/setting/components/sub-page'
import { usePatchSettings, useSettings } from '@/modules/setting/hooks/use-settings'
import { SkeletonList } from '@/shared/components/skeleton-list'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { formatDayTitle, toDateKey } from '@/shared/utils/format'
import { cn } from '@/shared/utils/cn'

const MODES = [
  { value: 'motorbike', label: 'Xe máy' },
  { value: 'car', label: 'Ô tô' },
  { value: 'walk', label: 'Đi bộ' },
] as const

// Ba tuyến phà quen (41 mục 5.4, QĐ-26); Google không có giờ phà nên người dùng tự nhập.
const DEFAULT_FERRIES: Ferry[] = ['Vũng Tàu – Cần Giờ', 'Cát Lái', 'Bình Khánh'].map((name) => ({
  name,
  place_query: `Bến phà ${name}`,
  first_time: null,
  last_time: null,
  hotline: null,
  note: null,
  updated_at: null,
}))

const STALE_DAYS = 180

function FerryEditor({ initial, saving, onSave }: { initial: Ferry[]; saving: boolean; onSave: (ferries: Ferry[]) => void }) {
  const [rows, setRows] = useState<Ferry[]>(() => DEFAULT_FERRIES.map((def) => initial.find((f) => f.name === def.name) ?? def))
  const [now] = useState(() => Date.now())
  const set = (index: number, patch: Partial<Ferry>) => setRows(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  const save = () => {
    // Ngày cập nhật dạng YYYY-MM-DD (thỏa thuận với agent Google ở mục 5 bảng việc).
    const today = toDateKey(new Date())
    onSave(rows.map((row, i) => (JSON.stringify(row) === JSON.stringify(initial.find((f) => f.name === row.name) ?? DEFAULT_FERRIES[i]) ? row : { ...row, updated_at: today })))
  }
  return (
    <div className="flex flex-col gap-4">
      {rows.map((row, index) => {
        const stale = row.updated_at ? (now - Date.parse(row.updated_at)) / 86_400_000 > STALE_DAYS : false
        return (
          <div key={row.name} className="flex flex-col gap-2 border-b pb-4 last:border-b-0 last:pb-0">
            <p className="flex items-center gap-2 text-sm font-medium">
              <Ship className="size-4 text-primary" />
              {row.name}
            </p>
            <div className="grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-1">
                <Label htmlFor={`ferry-first-${index}`} className="text-xs">
                  Chuyến đầu
                </Label>
                <Input id={`ferry-first-${index}`} type="time" value={row.first_time ?? ''} onChange={(e) => set(index, { first_time: e.target.value || null })} />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor={`ferry-last-${index}`} className="text-xs">
                  Chuyến cuối
                </Label>
                <Input id={`ferry-last-${index}`} type="time" value={row.last_time ?? ''} onChange={(e) => set(index, { last_time: e.target.value || null })} />
              </div>
            </div>
            <Input aria-label={`Hotline ${row.name}`} inputMode="tel" placeholder="Hotline" value={row.hotline ?? ''} onChange={(e) => set(index, { hotline: e.target.value || null })} />
            <Input aria-label={`Ghi chú ${row.name}`} placeholder="Ghi chú, ví dụ cuối tuần thêm chuyến" value={row.note ?? ''} onChange={(e) => set(index, { note: e.target.value || null })} />
            <p className={cn('text-xs text-muted-foreground', stale && 'text-warning')}>
              {row.updated_at
                ? `Cập nhật ${formatDayTitle(toDateKey(row.updated_at)).split(', ')[1]}${stale ? ': đã quá 180 ngày, trợ lý sẽ nhắc gọi hotline' : ''}`
                : 'Chưa nhập giờ: trợ lý sẽ nhắc gọi hotline'}
            </p>
          </div>
        )
      })}
      <Button disabled={saving} onClick={save}>
        {saving && <Loader2 className="size-4 animate-spin" />}
        Lưu giờ phà
      </Button>
    </div>
  )
}

function NumberField({ id, label, value, step, onCommit }: { id: string; label: string; value: number; step: number; onCommit: (value: number) => void }) {
  const [text, setText] = useState(String(value).replace('.', ','))
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        inputMode="decimal"
        className="w-24 text-right"
        value={text}
        step={step}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => {
          const parsed = Number(text.replace(',', '.'))
          if (Number.isFinite(parsed) && parsed !== value) onCommit(parsed)
          else setText(String(value).replace('.', ','))
        }}
      />
    </div>
  )
}

// Lịch trình trong Cài đặt: phương tiện mặc định, khung giờ chạy đêm, nghỉ sau bao lâu, hệ số chậm, giờ phà quen.
export function TripSettingsPage() {
  const settings = useSettings()
  const patch = usePatchSettings()
  const v = settings.data
  const save = (values: Partial<SettingValues>) => patch.mutate(values)
  return (
    <SubPage title="Lịch trình" subtitle="Luật đánh giá chuyến và giờ phà quen">
      {!v && <SkeletonList />}
      {v && (
        <>
          <SettingSection title="Đánh giá chuyến">
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-2 text-sm">
                <span>Phương tiện mặc định</span>
                <div className="grid grid-cols-3 gap-2">
                  {MODES.map((mode) => (
                    <button
                      key={mode.value}
                      type="button"
                      onClick={() => save({ 'trip.default_travel_mode': mode.value })}
                      className={cn('rounded-xl border py-2', v['trip.default_travel_mode'] === mode.value && 'border-primary bg-primary/15 text-primary')}
                    >
                      {mode.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex flex-col gap-2 text-sm">
                <span>Khung chạy đêm (luật R5)</span>
                <div className="grid grid-cols-2 gap-2">
                  <Input aria-label="Giờ bắt đầu chạy đêm" type="time" defaultValue={v['trip.night_start']} onBlur={(e) => e.target.value !== v['trip.night_start'] && save({ 'trip.night_start': e.target.value })} />
                  <Input aria-label="Giờ hết chạy đêm" type="time" defaultValue={v['trip.night_end']} onBlur={(e) => e.target.value !== v['trip.night_end'] && save({ 'trip.night_end': e.target.value })} />
                </div>
              </div>
              <NumberField id="ride-break" label="Nhắc nghỉ sau (phút chạy liền)" value={v['trip.ride_break_minutes']} step={5} onCommit={(n) => save({ 'trip.ride_break_minutes': Math.round(n) })} />
              <NumberField id="speed-factor" label="Hệ số chậm so với Google" value={v['trip.speed_factor']} step={0.1} onCommit={(n) => save({ 'trip.speed_factor': n })} />
              <p className="text-xs text-muted-foreground">Hệ số 1,2 nghĩa là tính giờ chạy dài hơn Google ước tính 20%.</p>
            </div>
          </SettingSection>
          <SettingSection title="Giờ phà quen">
            <FerryEditor
              initial={v['trip.ferries'] ?? []}
              saving={patch.isPending}
              onSave={(ferries) => patch.mutate({ 'trip.ferries': ferries }, { onSuccess: () => toast.success('Đã lưu giờ phà') })}
            />
          </SettingSection>
        </>
      )}
    </SubPage>
  )
}
