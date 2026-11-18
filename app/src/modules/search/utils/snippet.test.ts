import { describe, expect, it } from 'vitest'
import { splitSnippet } from '@/modules/search/utils/snippet'

describe('splitSnippet', () => {
  it('tách chữ in đậm', () => {
    expect(splitSnippet('... gia hạn <b>hợp đồng nhà</b> tới 12/2027')).toEqual([
      { text: '... gia hạn ', bold: false },
      { text: 'hợp đồng nhà', bold: true },
      { text: ' tới 12/2027', bold: false },
    ])
  })

  it('bỏ thẻ lạ, giải mã thực thể', () => {
    expect(splitSnippet('<img src=x onerror=alert(1)>a &amp; <b>b</b>')).toEqual([
      { text: 'a & ', bold: false },
      { text: 'b', bold: true },
    ])
  })
})
