import { useRef, useState, type FormEvent } from 'react'
import { Loader2, Trash2 } from 'lucide-react'
import { getErrorMessage } from '@/core/api/api-error'
import { useDeleteTask, useSaveTask } from '@/modules/calendar/hooks/use-calendar'
import type { Task, TaskPriority } from '@/modules/calendar/types/calendar'
import { fromLocalInput, toLocalInput } from '@/modules/calendar/utils/calendar-dates'
import { Button } from '@/shared/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Textarea } from '@/shared/ui/textarea'
import { cn } from '@/shared/utils/cn'

type DueKind = 'none' | 'date' | 'time'

const PRIORITIES: { value: TaskPriority; label: string }[] = [
  { value: 'low', label: 'Thấp' },
  { value: 'normal', label: 'Thường' },
  { value: 'high', label: 'Cao' },
]

const DUE_KINDS: { value: DueKind; label: string }[] = [
  { value: 'none', label: 'Không hạn' },
  { value: 'date', label: 'Ngày' },
  { value: 'time', label: 'Ngày giờ' },
]

interface TaskDialogProps {
  task: Task | null
  dayKey: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

// Hộp sửa việc. Có ngày không giờ: đi Google Tasks; có giờ: thành sự kiện lịch và được nhắc trên máy (40 mục 5).
export function TaskDialog({ task, dayKey, open, onOpenChange }: TaskDialogProps) {
  const save = useSaveTask()
  const remove = useDeleteTask()
  const [title, setTitle] = useState(task?.title ?? '')
  const [note, setNote] = useState(task?.note ?? '')
  const [priority, setPriority] = useState<TaskPriority>(task?.priority ?? 'normal')
  const [dueKind, setDueKind] = useState<DueKind>(task?.due_at ? 'time' : task?.due_date ? 'date' : task ? 'none' : 'date')
  const [dueDate, setDueDate] = useState(task?.due_date ?? dayKey)
  const [dueAt, setDueAt] = useState(task?.due_at ? toLocalInput(task.due_at) : `${dayKey}T17:00`)
  const [error, setError] = useState('')
  const savingRef = useRef(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (savingRef.current) return
    if (!title.trim()) {
      setError('Cần tên việc.')
      return
    }
    savingRef.current = true
    setError('')
    try {
      await save.mutateAsync({
        id: task?.id ?? null,
        input: {
          title: title.trim(),
          note: note.trim() || null,
          priority,
          due_date: dueKind === 'date' ? dueDate : null,
          due_at: dueKind === 'time' ? fromLocalInput(dueAt) : null,
        },
      })
      onOpenChange(false)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      savingRef.current = false
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{task ? 'Việc' : 'Thêm việc'}</DialogTitle>
          <DialogDescription>{dueKind === 'time' ? 'Việc có giờ nằm trên lịch và được nhắc trên máy.' : 'Việc có ngày đồng bộ sang Google Tasks.'}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="task-title">Tên việc</Label>
            <Input id="task-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Gửi báo giá" maxLength={1024} required />
          </div>
          <div className="flex flex-col gap-2">
            <Label>Ưu tiên</Label>
            <div className="grid grid-cols-3 gap-2">
              {PRIORITIES.map((p) => (
                <button key={p.value} type="button" onClick={() => setPriority(p.value)} className={cn('rounded-xl border py-2 text-sm', priority === p.value && 'border-primary bg-primary/15 text-primary')}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label>Hạn</Label>
            <div className="grid grid-cols-3 gap-2">
              {DUE_KINDS.map((k) => (
                <button key={k.value} type="button" onClick={() => setDueKind(k.value)} className={cn('rounded-xl border py-2 text-sm', dueKind === k.value && 'border-primary bg-primary/15 text-primary')}>
                  {k.label}
                </button>
              ))}
            </div>
            {dueKind === 'date' && <Input aria-label="Ngày hạn" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} required />}
            {dueKind === 'time' && <Input aria-label="Giờ hạn" type="datetime-local" value={dueAt} onChange={(e) => setDueAt(e.target.value)} required />}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="task-note">Ghi chú</Label>
            <Textarea id="task-note" value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={8000} />
          </div>
          {error && (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            {task && (
              <Button
                type="button"
                variant="ghost"
                className="text-destructive"
                onClick={() => {
                  remove.mutate(task.id)
                  onOpenChange(false)
                }}
              >
                <Trash2 className="size-4" />
                Xóa
              </Button>
            )}
            <Button type="submit" className="ml-auto" disabled={save.isPending}>
              {save.isPending && <Loader2 className="size-4 animate-spin" />}
              Lưu
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
