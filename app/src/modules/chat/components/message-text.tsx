import { RichText } from '@/shared/components/rich-text'

// Chữ trả lời: giữ xuống dòng, in đậm **...**, link và số điện thoại bấm được (QĐ-44). Không dựng HTML.
export function MessageText({ text }: { text: string }) {
  return <RichText text={text} />
}
