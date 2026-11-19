import { describe, expect, it } from 'vitest'
import { parseEmails, threadIdFromKey } from '@/modules/inbox/api/gmail-api'

describe('soạn thư', () => {
  it('tách email, bỏ trùng, báo email sai', () => {
    expect(parseEmails('Minh@Example.com, lan@example.com; minh@example.com  sai@')).toEqual({ valid: ['minh@example.com', 'lan@example.com'], invalid: ['sai@'] })
    expect(parseEmails('   ')).toEqual({ valid: [], invalid: [] })
  })

  it('id luồng từ conversation_key', () => {
    expect(threadIdFromKey('gmail:18c2f')).toBe('18c2f')
    expect(threadIdFromKey('18c2f')).toBe('18c2f')
  })
})
