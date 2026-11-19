import { describe, expect, it } from 'vitest'
import { parseInline, parseMarkdown } from '@/shared/utils/markdown'
import { guessMime, isMarkdownFile } from '@/shared/utils/mime'
import { tokenizeText } from '@/shared/utils/text-tokens'

describe('mime theo đuôi', () => {
  it('mime rỗng hoặc octet-stream thì suy theo đuôi', () => {
    expect(guessMime('ghi-chu.md', '')).toBe('text/markdown')
    expect(guessMime('ghi-chu.MD', 'application/octet-stream')).toBe('text/markdown')
    expect(guessMime('a.txt', null)).toBe('text/plain')
    expect(guessMime('a.docx', '')).toBe('application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    expect(guessMime('IMG.HEIC', '')).toBe('image/heic')
    expect(guessMime('anh.png', 'image/png')).toBe('image/png')
    expect(guessMime('la.xyz', '')).toBe('application/octet-stream')
  })

  it('nhận tệp Markdown', () => {
    expect(isMarkdownFile('a.md')).toBe(true)
    expect(isMarkdownFile('a.txt', 'text/markdown')).toBe(true)
    expect(isMarkdownFile('a.pdf', 'application/pdf')).toBe(false)
  })
})

describe('chữ tin nhắn', () => {
  it('link bấm được, bỏ dấu câu ở cuối', () => {
    expect(tokenizeText('Xem https://example.com/a?b=1, nhé')).toEqual([
      { type: 'text', value: 'Xem ' },
      { type: 'link', value: 'https://example.com/a?b=1', href: 'https://example.com/a?b=1' },
      { type: 'text', value: ', nhé' },
    ])
    expect(tokenizeText('vào www.zalo.me.')[1]).toEqual({ type: 'link', value: 'www.zalo.me', href: 'https://www.zalo.me' })
  })

  it('số điện thoại Việt Nam bấm gọi được', () => {
    expect(tokenizeText('Gọi 0909 123 456 nhé')[1]).toEqual({ type: 'phone', value: '0909 123 456', href: 'tel:0909123456' })
    expect(tokenizeText('Số +84909123456')[1]).toEqual({ type: 'phone', value: '+84909123456', href: 'tel:+84909123456' })
  })

  it('số ngắn, mã đơn không thành số điện thoại', () => {
    expect(tokenizeText('Mã 123456 hết hạn').every((t) => t.type === 'text')).toBe(true)
    expect(tokenizeText('Tổng 45.000 đ').every((t) => t.type === 'text')).toBe(true)
  })

  it('in đậm', () => {
    expect(tokenizeText('Ghi **45k** cơm')).toEqual([
      { type: 'text', value: 'Ghi ' },
      { type: 'bold', value: '45k' },
      { type: 'text', value: ' cơm' },
    ])
  })
})

describe('Markdown', () => {
  it('tách khối', () => {
    const blocks = parseMarkdown('# Tiêu đề\n\nĐoạn một\ndòng hai\n\n- a\n- b\n\n1. x\n2. y\n\n> trích\n\n```js\nconst a = 1\n```\n\n---')
    expect(blocks.map((b) => b.type)).toEqual(['heading', 'paragraph', 'list', 'list', 'quote', 'code', 'hr'])
    expect(blocks[1]).toEqual({ type: 'paragraph', text: 'Đoạn một\ndòng hai' })
    expect(blocks[2]).toEqual({ type: 'list', ordered: false, items: ['a', 'b'] })
    expect(blocks[3]).toEqual({ type: 'list', ordered: true, items: ['x', 'y'] })
    expect(blocks[5]).toEqual({ type: 'code', lang: 'js', text: 'const a = 1' })
  })

  it('chữ trong dòng; link chỉ nhận https, mailto, tel', () => {
    expect(parseInline('**đậm** *nghiêng* `mã` [web](https://a.vn) [x](javascript:alert(1))')).toEqual([
      { type: 'strong', value: 'đậm' },
      { type: 'text', value: ' ' },
      { type: 'em', value: 'nghiêng' },
      { type: 'text', value: ' ' },
      { type: 'code', value: 'mã' },
      { type: 'text', value: ' ' },
      { type: 'link', value: 'web', href: 'https://a.vn' },
      { type: 'text', value: ' ' },
      { type: 'text', value: 'x' },
      { type: 'text', value: ')' },
    ])
  })
})
