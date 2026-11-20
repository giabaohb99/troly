import { describe, expect, it } from 'vitest'
import { accountRoleText, defaultSenderId, sortAccounts, type GoogleAccount } from '@/shared/api/google-accounts-api'

const acc = (id: number, email: string, role: GoogleAccount['role'], status: GoogleAccount['status'] = 'active'): GoogleAccount => ({
  id,
  email,
  role,
  status,
  last_sync_at: null,
  last_error: null,
})

describe('nhiều tài khoản Gmail (QĐ-50)', () => {
  const primary = acc(1, 'giabao@gmail.com', 'primary')
  const work = acc(2, 'bao.congviec@gmail.com', 'mail')

  it('tài khoản chính đứng đầu; chữ vai trò', () => {
    expect(sortAccounts([work, primary]).map((a) => a.id)).toEqual([1, 2])
    expect(accountRoleText(primary)).toBe('Chính: Lịch, Việc, Gmail')
    expect(accountRoleText(work)).toBe('Thêm: chỉ Gmail')
  })

  it('gửi từ: tài khoản nhận luồng thư khi trả lời, không thì tài khoản chính', () => {
    expect(defaultSenderId([primary, work], 'Bao.CongViec@gmail.com')).toBe(2)
    expect(defaultSenderId([primary, work], null)).toBe(1)
    expect(defaultSenderId([primary, work], 'khong-con@gmail.com')).toBe(1)
  })

  it('bỏ tài khoản đã thu hồi; không còn tài khoản thì null', () => {
    expect(defaultSenderId([primary, acc(3, 'cu@gmail.com', 'mail', 'revoked')], 'cu@gmail.com')).toBe(1)
    expect(defaultSenderId([], null)).toBeNull()
  })
})
