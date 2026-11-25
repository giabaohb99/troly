import { describe, expect, it } from 'vitest'
import { parseInline, parseMarkdown } from '@/shared/utils/markdown'
import { guessMime, isMarkdownFile } from '@/shared/utils/mime'
import { linkHost, reflowPlainText, tokenizeText } from '@/shared/utils/text-tokens'

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

describe('link trong thư và Hộp tin (phản hồi 1.0.8)', () => {
  it('email thành link soạn thư; email trong link không tách riêng', () => {
    expect(tokenizeText('Gửi về hgbao.idagroup@gmail.com nhé.')).toEqual([
      { type: 'text', value: 'Gửi về ' },
      { type: 'email', value: 'hgbao.idagroup@gmail.com', href: 'mailto:hgbao.idagroup@gmail.com' },
      { type: 'text', value: ' nhé.' },
    ])
    const inLink = tokenizeText('https://x.vn/huy?email=a@b.com')
    expect(inLink).toHaveLength(1)
    expect(inLink[0].type).toBe('link')
  })

  it('tên miền của link dài', () => {
    expect(linkHost('https://dashboard.render.com/web/srv-abc123/settings?utm_source=email')).toBe('dashboard.render.com')
    expect(linkHost('https://www.booking.com/x')).toBe('booking.com')
  })

  it('gộp dòng bị ngắt giữa câu, giữ đoạn, lời chào, gạch đầu dòng', () => {
    const text = [
      'Chào anh Bảo,',
      '',
      'Hóa đơn tháng 11 của dịch vụ Render đã sẵn sàng, tổng cộng 7 USD, sẽ được',
      'trừ vào thẻ vào ngày 1 tháng 12.',
      '- Web service: 7 USD',
      '- Database: 0 USD',
      '',
      'Trân trọng,',
      'Render',
    ].join('\r\n')
    expect(reflowPlainText(text)).toBe(
      [
        'Chào anh Bảo,',
        '',
        'Hóa đơn tháng 11 của dịch vụ Render đã sẵn sàng, tổng cộng 7 USD, sẽ được trừ vào thẻ vào ngày 1 tháng 12.',
        '- Web service: 7 USD',
        '- Database: 0 USD',
        '',
        'Trân trọng,',
        'Render',
      ].join('\n'),
    )
    expect(reflowPlainText('a\n\n\n\nb')).toBe('a\n\nb')
  })
})

describe('tổng đài 1800, 1900 (phản hồi 1.0.8)', () => {
  it('bấm gọi được; số dài ngắn sai không thành link', () => {
    expect(tokenizeText('gọi 1800 1091 nhé')[1]).toEqual({ type: 'phone', value: '1800 1091', href: 'tel:18001091' })
    expect(tokenizeText('1900 6600 99')[0]).toEqual({ type: 'phone', value: '1900 6600 99', href: 'tel:1900660099' })
    expect(tokenizeText('mã 180012').every((t) => t.type === 'text')).toBe(true)
  })
})

