import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { Alarm } from '@/core/native/alarm'
import {
  completeTask,
  createTask,
  deleteEvent,
  deleteTask,
  listEvents,
  listTasks,
  reopenTask,
  resolveRemoteDelete,
  restoreEvent,
  restoreTask,
  updateTask,
} from '@/modules/calendar/api/calendar-api'
import type { Task, TaskInput } from '@/modules/calendar/types/calendar'
import { queryKeys } from '@/shared/constants/query-keys'

export function useEvents(range: { from: string; to: string }) {
  return useQuery({ queryKey: queryKeys.calendar.events(range), queryFn: () => listEvents(range.from, range.to), select: (data) => data.items })
}

export function useTasks(status: 'todo' | 'done') {
  return useQuery({
    queryKey: queryKeys.calendar.tasks(status),
    queryFn: () => listTasks(status, status === 'todo' ? 200 : 30),
    select: (data) => data.items,
  })
}

// Sau mọi lần sửa lịch hoặc việc: tải lại danh sách và nhờ lớp gốc tải lại nhắc ngay (30 mục 3.9).
export function useInvalidateCalendar() {
  const queryClient = useQueryClient()
  return () => {
    void Alarm.sync()
    return queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all })
  }
}

export function useSaveTask() {
  const invalidate = useInvalidateCalendar()
  return useMutation({
    mutationFn: ({ id, input }: { id: number | null; input: TaskInput }) => (id ? updateTask(id, input) : createTask(input)),
    onSuccess: () => invalidate(),
  })
}

// Tích xong làm ngay, toast có Hoàn tác (31 mục 3.5).
export function useToggleTask() {
  const invalidate = useInvalidateCalendar()
  return useMutation({
    mutationFn: (task: Task) => (task.status === 'done' ? reopenTask(task.id) : completeTask(task.id)),
    onSuccess: (_data, task) => {
      void invalidate()
      if (task.status === 'done') return
      toast.success('Đã xong việc', {
        duration: 8_000,
        action: {
          label: 'Hoàn tác',
          onClick: () =>
            void reopenTask(task.id)
              .then(() => invalidate())
              .catch((error: unknown) => toast.error(getErrorMessage(error))),
        },
      })
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
}

export function useDeleteTask() {
  const invalidate = useInvalidateCalendar()
  return useMutation({
    mutationFn: (id: number) => deleteTask(id),
    onSuccess: (_data, id) => {
      void invalidate()
      toast.success('Đã xóa việc', {
        duration: 8_000,
        action: {
          label: 'Hoàn tác',
          onClick: () =>
            void restoreTask(id)
              .then(() => invalidate())
              .catch((error: unknown) => toast.error(getErrorMessage(error))),
        },
      })
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
}

// Việc bị xóa trên Google Tasks: người dùng chọn xóa luôn hay giữ lại (QĐ-21).
export function useResolveRemoteDelete() {
  const invalidate = useInvalidateCalendar()
  return useMutation({
    mutationFn: ({ id, keep }: { id: number; keep: boolean }) => resolveRemoteDelete(id, keep),
    onSuccess: (_data, { keep }) => {
      void invalidate()
      toast.success(keep ? 'Đã giữ lại việc, sẽ tạo lại trên Google Tasks' : 'Đã xóa việc')
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
}

// Xóa sự kiện không khách: làm ngay, có Hoàn tác. Có khách: máy chủ trả việc chờ duyệt (xử lý ở hộp sửa).
export function useDeleteEvent() {
  const invalidate = useInvalidateCalendar()
  return useMutation({
    mutationFn: ({ id, occurrenceStart }: { id: number; occurrenceStart: string | null }) => deleteEvent(id, occurrenceStart),
    onSuccess: (result, { id, occurrenceStart }) => {
      void invalidate()
      if (result) return
      toast.success('Đã xóa sự kiện', {
        duration: 8_000,
        action: occurrenceStart
          ? undefined
          : {
              label: 'Hoàn tác',
              onClick: () =>
                void restoreEvent(id)
                  .then(() => invalidate())
                  .catch((error: unknown) => toast.error(getErrorMessage(error))),
            },
      })
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
}
