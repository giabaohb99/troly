import { describe, expect, it } from 'vitest'
import { FEATURES_OFF, readFeatures } from '@/shared/hooks/use-features'

describe('cờ tính năng (đợt 1.1.0)', () => {
  it('máy chủ cũ không có cờ, lỗi dạng thì tắt hết', () => {
    expect(readFeatures({ jobs: [] })).toEqual(FEATURES_OFF)
    expect(readFeatures(null)).toEqual(FEATURES_OFF)
    expect(readFeatures({ features: 'gym' })).toEqual(FEATURES_OFF)
  })

  it('chỉ true mới bật', () => {
    expect(readFeatures({ features: { gym: true, connectors: 'yes', zalo_bridge: 1 } })).toEqual({ gym: true, connectors: false, zalo_bridge: false })
  })
})
