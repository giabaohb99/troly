import { describe, expect, it } from 'vitest'
import { deepLinkToRoute } from '@/shared/utils/deep-link'

describe('deepLinkToRoute', () => {
  it.each([
    ['chat/52?tin=884', '/?phien=52&tin=884'],
    ['chat/52?tin=884&mo-tep=91', '/?phien=52&tin=884&mo-tep=91'],
    ['chat/52', '/?phien=52'],
    ['?phien=52&tin=884', '/?phien=52&tin=884'],
    ['lich/su-kien/9', '/lich/su-kien/9'],
    ['cai-dat/google?ket-qua=ok', '/cai-dat/google?ket-qua=ok'],
    ['chi-tieu?sua=5', '/chi-tieu?sua=5'],
  ])('%s', (path, route) => {
    expect(deepLinkToRoute(path)).toBe(route)
  })
})
