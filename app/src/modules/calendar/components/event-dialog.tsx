import { useRef, useState, type FormEvent } from 'react'
import { AlarmClock, Loader2, Lock, Repeat, Trash2, X } from 'lucide-react'
import { getErrorMessage } from '@/core/api/api-error'
import { confirmOf, createEvent, isPending, updateEvent } from '@/modules/calendar/api/calendar-api'
import { useDeleteEvent, useInvalidateCalendar } from '@/modules/calendar/hooks/use-calendar'
import type { CalendarEvent, EventInput, RemindSource } from '@/modules/calendar/types/calendar'
import { addDays, fromLocalInput, toLocalInput } from '@/modules/calendar/utils/calendar-dates'
import { ConfirmCard } from '@/shared/components/confirm-card'
import type { ConfirmInfo } from '@/shared/types/pending-action'
import { Button } from '@/shared/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Switch } from '@/shared/ui/switch'
import { Textarea } from '@/shared/ui/textarea'
import { cn } from '@/shared/utils/cn'

const REMIND_OPTIONS = [0, 5, 15, 30, 60]
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

interface EventDialogProps {
  event: CalendarEvent | null
  // Ngày đang xem, dùng làm ngày mặc định khi thêm mới.
  dayKey: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

function defaultStart(dayKey: string): string {
  const now = new Date()
  const nowLocal = toLocalInput(now.toISOString())
  if (nowLocal.slice(0, 10) === dayKey) {
    const hour = Math.min(23, Number(nowLocal.slice(11, 13)) + 1)
    return `${dayKey}T${String(hour).padStart(2, '0')}:00`
  }
  return `${dayKey}T09:00`
}

function plusHour(local: string): string {
  return toLocalInput(new Date(Date.parse(fromLocalInput(local)) + 3_600_000).toISOString())
}

// Hộp sửa sự kiện (31 mục 3.5). Có khách: lưu xong hiện thẻ duyệt ngay trong hộp (QĐ-23), duyệt rồi mới ghi.
// Sự kiện người khác mời: chỉ đổi được Ai nhắc.
export function EventDialog({ event, dayKey, open, onOpenChange }: EventDialogProps) {
  const invalidate = useInvalidateCalendar()
  const remove = useDeleteEvent()
  const readOnly = event?.is_organizer === false
  const [title, setTitle] = useState(event?.title ?? '')
  const [allDay, setAllDay] = useState(event?.all_day ?? false)
  const [start, setStart] = useState(() => (event?.start_at ? toLocalInput(event.start_at) : defaultStart(dayKey)))
  const [end, setEnd] = useState(() => (event?.end_at ? toLocalInput(event.end_at) : plusHour(event?.start_at ? toLocalInput(event.start_at) : defaultStart(dayKey))))
  const [startDate, setStartDate] = useState(event?.start_date ?? dayKey)
  const [endDate, setEndDate] = useState(event?.end_date ? addDays(event.end_date, -1) : (event?.start_date ?? dayKey))
  const [location, setLocation] = useState(event?.location ?? '')
  const [attendees, setAttendees] = useState<string[]>(() => (event?.attendees ?? []).filter((a) => !a.is_self).map((a) => a.email))
  const [guestText, setGuestText] = useState('')
  const [remindSource, setRemindSource] = useState<RemindSource>(event?.remind_source ?? 'app')
  const [remindMinutes, setRemindMinutes] = useState<number | null>(event ? (event.remind_minutes.length ? Math.min(...event.remind_minutes) : null) : 15)
  const [isAlarm, setIsAlarm] = useState(event?.is_alarm ?? false)
  const [description, setDescription] = useState(event?.description ?? '')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [pending, setPending] = useState<ConfirmInfo | null>(null)
  const savingRef = useRef(false)
  const occurrence = event?.occurrence_start ?? null

  function addGuest() {
    const email = guestText.trim().toLowerCase()
    if (!email) return
    if (!EMAIL_RE.test(email)) {
      setError('Email khách chưa đúng.')
      return
    }
    setError('')
    if (!attendees.includes(email)) setAttendees([...attendees, email])
    setGuestText('')
  }

  function buildInput(): EventInput | Partial<EventInput> {
    const remind = { remind_source: remindSource, remind_minutes: remindSource === 'app' && remindMinutes !== null ? [remindMinutes] : [], is_alarm: remindSource === 'app' && isAlarm }
    if (readOnly) return remind
    return {
      title: title.trim(),
      description: description.trim() || null,
      location: location.trim() || null,
      all_day: allDay,
      ...(allDay
        ? { start_date: startDate, end_date: addDays(endDate < startDate ? startDate : endDate, 1), start_at: null, end_at: null }
        : { start_at: fromLocalInput(start), end_at: fromLocalInput(end < start ? start : end), start_date: null, end_date: null }),
      ...remind,
      attendees,
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (savingRef.current) return
    if (!readOnly && !title.trim()) {
      setError('Cần tiêu đề.')
      return
    }
    if (guestText.trim()) addGuest()
    savingRef.current = true
    setSaving(true)
    setError('')
    try {
      const input = buildInput()
      const result = event ? await updateEvent(event.id, input, occurrence) : await createEvent(input as EventInput)
      if (isPending(result)) {
        const count = attendees.length
        setPending(confirmOf(result.pending_action, count ? `Gửi lời mời tới ${count} người` : 'Duyệt'))
      } else {
        void invalidate()
        onOpenChange(false)
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!event) return
    try {
      const result = await remove.mutateAsync({ id: event.id, occurrenceStart: occurrence })
      if (result && isPending(result)) setPending(confirmOf(result.pending_action, 'Xóa và báo khách'))
      else onOpenChange(false)
    } catch {
      // Toast lỗi đã hiện trong hook.
    }
  }

  const locked = readOnly || !!pending

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{event ? 'Sự kiện' : 'Thêm sự kiện'}</DialogTitle>
          <DialogDescription className="flex items-center gap-1">
            {readOnly ? (
              <>
                <Lock className="size-3.5" /> Sự kiện của người khác, chỉ đổi được Ai nhắc.
              </>
            ) : event?.is_recurring ? (
              <>
                <Repeat className="size-3.5" /> Sự kiện lặp: chỉ sửa lần này.
              </>
            ) : (
              'Lưu sự kiện có khách thì cần duyệt trước khi gửi lời mời.'
            )}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="event-title">Tiêu đề</Label>
            <Input id="event-title" value={title} disabled={locked} onChange={(e) => setTitle(e.target.value)} placeholder="Họp nhóm" maxLength={500} required={!readOnly} />
          </div>

          <label className="flex items-center justify-between text-sm">
            Cả ngày
            <Switch checked={allDay} disabled={locked} onCheckedChange={setAllDay} />
          </label>

          {allDay ? (
            <div className="grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="event-start-date">Từ ngày</Label>
                <Input id="event-start-date" type="date" value={startDate} disabled={locked} onChange={(e) => setStartDate(e.target.value)} required />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="event-end-date">Tới ngày</Label>
                <Input id="event-end-date" type="date" value={endDate} min={startDate} disabled={locked} onChange={(e) => setEndDate(e.target.value)} required />
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <Label htmlFor="event-start">Bắt đầu</Label>
              <Input
                id="event-start"
                type="datetime-local"
                value={start}
                disabled={locked}
                onChange={(e) => {
                  const value = e.target.value
                  if (value && end <= start) setEnd(plusHour(value))
                  else if (value) setEnd(toLocalInput(new Date(Date.parse(fromLocalInput(end)) + Date.parse(fromLocalInput(value)) - Date.parse(fromLocalInput(start))).toISOString()))
                  setStart(value)
                }}
                required
              />
              <Label htmlFor="event-end">Kết thúc</Label>
              <Input id="event-end" type="datetime-local" value={end} min={start} disabled={locked} onChange={(e) => setEnd(e.target.value)} required />
            </div>
          )}

          <div className="flex flex-col gap-2">
            <Label htmlFor="event-location">Địa điểm</Label>
            <Input id="event-location" value={location} disabled={locked} onChange={(e) => setLocation(e.target.value)} maxLength={500} />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="event-guest">Khách mời</Label>
            {attendees.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {attendees.map((email) => (
                  <span key={email} className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-xs">
                    {email}
                    {!locked && (
                      <button type="button" aria-label={`Bỏ ${email}`} onClick={() => setAttendees(attendees.filter((a) => a !== email))}>
                        <X className="size-3" />
                      </button>
                    )}
                  </span>
                ))}
              </div>
            )}
            {!locked && (
              <div className="flex gap-2">
                <Input
                  id="event-guest"
                  type="email"
                  inputMode="email"
                  value={guestText}
                  onChange={(e) => setGuestText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      addGuest()
                    }
                  }}
                  placeholder="email@..."
                />
                <Button type="button" variant="secondary" onClick={addGuest}>
                  Thêm
                </Button>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label>Ai nhắc</Label>
            <div className="grid grid-cols-2 gap-2">
              {(['app', 'google'] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  disabled={!!pending}
                  onClick={() => setRemindSource(value)}
                  className={cn('rounded-xl border py-2 text-sm', remindSource === value && 'border-primary bg-primary/15 text-primary')}
                >
                  {value === 'app' ? 'App nhắc' : 'Google nhắc'}
                </button>
              ))}
            </div>
            {remindSource === 'app' && (
              <>
                <div className="flex flex-wrap gap-2">
                  {REMIND_OPTIONS.map((minutes) => (
                    <button
                      key={minutes}
                      type="button"
                      disabled={!!pending}
                      onClick={() => setRemindMinutes(remindMinutes === minutes ? null : minutes)}
                      className={cn('rounded-full border px-3 py-1 text-sm', remindMinutes === minutes && 'border-primary bg-primary/15 text-primary')}
                    >
                      {minutes === 0 ? 'Đúng giờ' : `${minutes} phút`}
                    </button>
                  ))}
                </div>
                <label className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2">
                    <AlarmClock className="size-4 text-muted-foreground" />
                    Báo thức (kêu cả khi máy đang ngủ)
                  </span>
                  <Switch checked={isAlarm} disabled={!!pending || remindMinutes === null} onCheckedChange={setIsAlarm} />
                </label>
              </>
            )}
            {remindSource === 'google' && <p className="text-xs text-muted-foreground">Google gửi nhắc theo cài đặt của Google Calendar, app không nhắc.</p>}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="event-description">Ghi chú</Label>
            <Textarea id="event-description" value={description} disabled={locked} onChange={(e) => setDescription(e.target.value)} rows={2} maxLength={8000} />
          </div>

          {error && (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          )}

          {pending ? (
            <ConfirmCard
              action={pending}
              className="max-w-full"
              onDecided={(status) => {
                void invalidate()
                if (status === 'done' || status === 'rejected') onOpenChange(false)
              }}
            />
          ) : (
            <div className="flex gap-2">
              {event && !readOnly && (
                <Button type="button" variant="ghost" className="text-destructive" disabled={remove.isPending} onClick={() => void handleDelete()}>
                  <Trash2 className="size-4" />
                  Xóa
                </Button>
              )}
              <Button type="submit" className="ml-auto" disabled={saving}>
                {saving && <Loader2 className="size-4 animate-spin" />}
                Lưu
              </Button>
            </div>
          )}
        </form>
      </DialogContent>
    </Dialog>
  )
}
