import { describe, expect, it } from 'vitest'
import type { Conversation } from '@/modules/inbox/types/inbox'
import { ACCOUNT_COLORS, accountChoices, accountColor, accountShort, filterByAccount, sortByLatest } from '@/modules/inbox/utils/inbox-list'

const conv = (key: string, at: string, extra: Partial<Conversation> = {}): Conversation => ({
  conversation_key: key,
  app: 'gmail',
  title: key,
  is_group: false,
  last_sender: null,
  last_text: null,
  last_posted_at: at,
  unread_count: 0,
  importance: 'normal',
  is_private: false,
  account_email: 'giabao@gmail.com',
  ...extra,
})

describe('danh sách Hộp tin (phản hồi 1.0.7)', () => {
  it('xếp theo tin mới nhất; thư quan trọng cũ không đứng trên thư mới', () => {
    const items = [conv('cu-co-sao', '2026-11-12T09:00:00+07:00', { importance: 'important' }), conv('moi', '2026-11-20T08:00:00+07:00'), conv('giua', '2026-11-19T08:00:00+07:00')]
    expect(sortByLatest(items).map((c) => c.conversation_key)).toEqual(['moi', 'giua', 'cu-co-sao'])
  })

  it('lọc theo tài khoản nhận, không phân biệt hoa thường; null là tất cả', () => {
    const items = [conv('a', '2026-11-20T08:00:00Z'), conv('b', '2026-11-20T07:00:00Z', { account_email: 'hgbao.idagroup@gmail.com' })]
    expect(filterByAccount(items, 'HGBAO.idagroup@gmail.com').map((c) => c.conversation_key)).toEqual(['b'])
    expect(filterByAccount(items, null)).toHaveLength(2)
  })

  it('tên ngắn, danh sách chip, màu theo tài khoản', () => {
    expect(accountShort('hgbao.idagroup@gmail.com')).toBe('hgbao.idagroup')
    const items = [conv('a', '2026-11-20T08:00:00Z', { account_email: 'la@gmail.com' })]
    expect(accountChoices(['giabao@gmail.com', 'hgbao.idagroup@gmail.com'], items)).toEqual(['giabao@gmail.com', 'hgbao.idagroup@gmail.com', 'la@gmail.com'])
    // Tài khoản đã nối và danh sách `accounts` của máy chủ trùng nhau thì chỉ một chip.
    expect(accountChoices(['giabao@gmail.com', 'GIABAO@gmail.com', 'la@gmail.com'], [])).toEqual(['giabao@gmail.com', 'la@gmail.com'])
    expect(accountColor('giabao@gmail.com', ['giabao@gmail.com', 'x@gmail.com'])).toBe(ACCOUNT_COLORS[0])
    expect(accountColor('X@gmail.com', ['giabao@gmail.com', 'x@gmail.com'])).toBe(ACCOUNT_COLORS[1])
    expect(ACCOUNT_COLORS).toContain(accountColor('khac@gmail.com', []))
  })
})
