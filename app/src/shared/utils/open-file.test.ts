import { describe, expect, it } from 'vitest'
import { fileKindLabel, formatFileSize, isImageFile, truncateMiddle } from '@/shared/utils/open-file'

describe('thẻ tệp', () => {
  it('nhãn loại tệp theo mime hoặc đuôi', () => {
    expect(fileKindLabel('application/pdf', 'bao-cao.pdf')).toBe('PDF')
    expect(fileKindLabel('', 'ghi-chu.md')).toBe('Markdown')
    expect(fileKindLabel('application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'a.docx')).toBe('Word')
    expect(fileKindLabel('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'a.xlsx')).toBe('Excel')
    expect(fileKindLabel('application/octet-stream', 'chi-tieu.xlsx')).toBe('Excel')
    expect(fileKindLabel('text/plain', 'a.txt')).toBe('Tệp')
  })

  it('cỡ tệp', () => {
    expect(formatFileSize(512)).toBe('512 B')
    expect(formatFileSize(48_000)).toBe('47 KB')
    expect(formatFileSize(2_621_440)).toBe('2,5 MB')
    expect(formatFileSize(null)).toBe(null)
  })
})

describe('tệp đính kèm', () => {
  it('nhận ảnh theo mime hoặc đuôi', () => {
    expect(isImageFile('image/jpeg', 'a')).toBe(true)
    expect(isImageFile('', 'IMG_2026.HEIC')).toBe(true)
    expect(isImageFile('application/pdf', 'a.pdf')).toBe(false)
  })

  it('rút gọn giữa, giữ đuôi', () => {
    expect(truncateMiddle('hop-dong.pdf', 26)).toBe('hop-dong.pdf')
    const short = truncateMiddle('bao-cao-chi-tieu-thang-11-nam-2026-ban-cuoi.pdf', 26)
    expect(short.length).toBe(26)
    expect(short.startsWith('bao-cao-chi')).toBe(true)
    expect(short.endsWith('cuoi.pdf')).toBe(true)
    expect(short).toContain('…')
    expect(truncateMiddle('khong-co-duoi-tep-nao-ca-va-rat-dai', 20)).toHaveLength(20)
  })
})
