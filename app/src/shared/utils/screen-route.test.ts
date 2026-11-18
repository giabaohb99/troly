import { describe, expect, it } from 'vitest'
import { screenToRoute } from '@/shared/utils/screen-route'

describe('screenToRoute', () => {
  it.each([
    ['chat', null, '/'],
    ['chat', { conversation_id: 52, message_id: 884 }, '/?phien=52'],
    ['expense_detail', { expense_id: 5 }, '/chi-tieu?sua=5'],
    ['note_detail', { note_id: 3 }, '/tim?ghi-chu=3'],
    ['file_detail', { file_id: 77 }, '/tim?tep=77'],
    ['search', { q: 'hợp đồng' }, '/tim?q=h%E1%BB%A3p%20%C4%91%E1%BB%93ng'],
    ['settings_ai_cost', null, '/cai-dat/chi-phi'],
    ['settings_profile', null, '/cai-dat'],
    ['trip_detail', { trip_id: 1 }, '/lich-trinh/1'],
    ['trip_detail', { trip_id: 1, day_no: 2 }, '/lich-trinh/1?ngay=2'],
    ['trip_list', null, '/lich-trinh'],
    ['calendar_day', { date: '2026-11-20' }, '/lich?ngay=2026-11-20'],
    ['event_detail', { event_id: 9 }, '/lich/su-kien/9'],
    ['event_detail', { event_id: 9, occurrence_start: '2026-11-20T01:30:00Z' }, '/lich/su-kien/9?lan=2026-11-20T01%3A30%3A00Z'],
    ['task_list', null, '/lich?tab=viec'],
    ['task_detail', { task_id: 4 }, '/lich/viec/4'],
    ['settings_google', null, '/cai-dat/google'],
    ['settings_device_check', null, '/thiet-lap'],
    ['man_la', null, '/'],
  ])('%s', (screen, params, route) => {
    expect(screenToRoute(screen, params)).toBe(route)
  })
})
