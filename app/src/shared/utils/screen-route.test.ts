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
    ['settings_ai_cost', null, '/cai-dat'],
    ['trip_detail', { trip_id: 1 }, '/lich-trinh'],
    ['man_la', null, '/'],
  ])('%s', (screen, params, route) => {
    expect(screenToRoute(screen, params)).toBe(route)
  })
})
