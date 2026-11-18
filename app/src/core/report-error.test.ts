import { describe, expect, it } from 'vitest'
import { redactSecrets, shouldSend } from '@/core/report-error'

describe('redactSecrets', () => {
  it('che mã trong tiêu đề và JSON', () => {
    expect(redactSecrets('Authorization: Bearer abc.def-ghi')).toBe('Authorization: Bearer ***')
    expect(redactSecrets('{"password":"bimat123","x":1}')).toBe('{"password":"***","x":1}')
    expect(redactSecrets('refresh_token="rt_abc"')).toBe('refresh_token="***"')
  })
})

describe('shouldSend', () => {
  it('bỏ lỗi trùng trong 1 phút', () => {
    expect(shouldSend('k1', 1_000)).toBe(true)
    expect(shouldSend('k1', 30_000)).toBe(false)
    expect(shouldSend('k1', 62_000)).toBe(true)
  })
})
