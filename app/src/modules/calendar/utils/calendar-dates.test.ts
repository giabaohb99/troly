import { describe, expect, it } from 'vitest'
import type { CalendarEvent, Task } from '@/modules/calendar/types/calendar'
import { addDays, eventDayKeys, eventsByDay, groupTasks, monthGridKeys, remindLabel, viewRange, weekKeys } from '@/modules/calendar/utils/calendar-dates'

const event = (extra: Partial<CalendarEvent>): CalendarEvent => ({
  id: 1,
  occurrence_start: null,
  is_recurring: false,
  title: 'Họp',
  description: null,
  location: null,
  all_day: false,
  start_at: null,
  end_at: null,
  start_date: null,
  end_date: null,
  status: 'confirmed',
  remind_minutes: [],
  remind_source: 'app',
  is_alarm: false,
  attendees: [],
  source: 'app',
  task_id: null,
  sync_status: 'synced',
  google_html_link: null,
  ...extra,
})

const task = (id: number, extra: Partial<Task>): Task => ({
  id,
  title: `Việc ${id}`,
  note: null,
  status: 'todo',
  priority: 'normal',
  due_date: null,
  due_at: null,
  completed_at: null,
  completed_source: null,
  event_id: null,
  sync_status: 'synced',
  ...extra,
})

describe('ngày trên lịch', () => {
  it('cộng ngày qua tháng, qua năm', () => {
    expect(addDays('2026-11-30', 1)).toBe('2026-12-01')
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28')
  })

  it('tuần bắt đầu thứ Hai', () => {
    // 18/11/2026 là thứ Tư.
    expect(weekKeys('2026-11-18')[0]).toBe('2026-11-16')
    expect(weekKeys('2026-11-22')[6]).toBe('2026-11-22')
    expect(weekKeys('2026-11-23')[0]).toBe('2026-11-23')
  })

  it('lưới tháng 42 ô từ thứ Hai trước ngày 1', () => {
    const grid = monthGridKeys('2026-11-18')
    expect(grid).toHaveLength(42)
    expect(grid[0]).toBe('2026-10-26')
    expect(grid).toContain('2026-11-30')
  })

  it('khoảng tải theo kiểu xem, giờ Việt Nam, to không tính', () => {
    expect(viewRange('day', '2026-11-18')).toEqual({ from: '2026-11-16T00:00:00+07:00', to: '2026-11-23T00:00:00+07:00' })
    expect(viewRange('month', '2026-11-18')).toEqual({ from: '2026-10-26T00:00:00+07:00', to: '2026-12-07T00:00:00+07:00' })
  })
})

describe('sự kiện theo ngày', () => {
  it('sự kiện có giờ lấy ngày theo giờ Việt Nam', () => {
    // 17:30 UTC ngày 17 là 00:30 ngày 18 ở Việt Nam.
    expect(eventDayKeys(event({ start_at: '2026-11-17T17:30:00Z', end_at: '2026-11-17T18:30:00Z' }))).toEqual(['2026-11-18'])
  })

  it('sự kiện cả ngày: end_date không tính', () => {
    expect(eventDayKeys(event({ all_day: true, start_date: '2026-11-18', end_date: '2026-11-20' }))).toEqual(['2026-11-18', '2026-11-19'])
  })

  it('sự kiện qua nửa đêm nằm ở cả hai ngày; kết thúc đúng 0 giờ thì không sang ngày sau', () => {
    expect(eventDayKeys(event({ start_at: '2026-11-18T15:00:00Z', end_at: '2026-11-18T18:00:00Z' }))).toEqual(['2026-11-18', '2026-11-19'])
    expect(eventDayKeys(event({ start_at: '2026-11-18T15:00:00Z', end_at: '2026-11-18T17:00:00Z' }))).toEqual(['2026-11-18'])
  })

  it('trong một ngày: cả ngày đứng trước, rồi theo giờ', () => {
    const map = eventsByDay([
      event({ id: 2, start_at: '2026-11-18T08:00:00Z', end_at: '2026-11-18T09:00:00Z' }),
      event({ id: 3, all_day: true, start_date: '2026-11-18', end_date: '2026-11-19' }),
      event({ id: 4, start_at: '2026-11-18T02:00:00Z', end_at: '2026-11-18T03:00:00Z' }),
    ])
    expect(map.get('2026-11-18')?.map((e) => e.id)).toEqual([3, 4, 2])
  })

  it('so giờ thật khi chuỗi ISO khác múi', () => {
    const map = eventsByDay([
      event({ id: 5, start_at: '2026-11-18T08:00:00.000Z', end_at: '2026-11-18T09:00:00.000Z' }),
      event({ id: 6, start_at: '2026-11-18T09:00:00+07:00', end_at: '2026-11-18T10:00:00+07:00' }),
    ])
    expect(map.get('2026-11-18')?.map((e) => e.id)).toEqual([6, 5])
  })

  it('nhãn nguồn nhắc', () => {
    expect(remindLabel(event({ remind_source: 'app', remind_minutes: [15] }))).toBe("App 15'")
    expect(remindLabel(event({ remind_source: 'app', remind_minutes: [0] }))).toBe('App đúng giờ')
    expect(remindLabel(event({ remind_source: 'app', is_alarm: true, remind_minutes: [0] }))).toBe('Báo thức')
    expect(remindLabel(event({ remind_source: 'app', remind_minutes: [] }))).toBe(null)
    expect(remindLabel(event({ remind_source: 'google', remind_minutes: [] }))).toBe('Google')
  })
})

describe('nhóm việc', () => {
  it('chia Quá hạn, Hôm nay, Sắp tới, Không hạn, Đã xong', () => {
    const groups = groupTasks(
      [
        task(1, { due_date: '2026-11-17' }),
        task(2, { due_date: '2026-11-18' }),
        task(3, { due_at: '2026-11-18T16:30:00Z' }), // 23:30 ngày 18 giờ Việt Nam
        task(4, { due_date: '2026-11-25' }),
        task(5, {}),
        task(6, { status: 'done', due_date: '2026-11-10' }),
      ],
      '2026-11-18',
    )
    expect(groups.overdue.map((t) => t.id)).toEqual([1])
    expect(groups.today.map((t) => t.id)).toEqual([2, 3])
    expect(groups.upcoming.map((t) => t.id)).toEqual([4])
    expect(groups.none.map((t) => t.id)).toEqual([5])
    expect(groups.done.map((t) => t.id)).toEqual([6])
  })

  it('việc có giờ đã qua giờ trong hôm nay vẫn tính Hôm nay', () => {
    const groups = groupTasks([task(1, { due_at: '2026-11-18T01:00:00Z' })], '2026-11-18')
    expect(groups.today).toHaveLength(1)
  })
})
