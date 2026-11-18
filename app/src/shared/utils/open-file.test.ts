import { describe, expect, it } from 'vitest'
import { fileKindLabel, formatFileSize } from '@/shared/utils/open-file'

describe('thẻ tệp', () => {
  it('nhãn loại tệp theo mime hoặc đuôi', () => {
    expect(fileKindLabel('application/pdf', 'bao-cao.pdf')).toBe('PDF')
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
