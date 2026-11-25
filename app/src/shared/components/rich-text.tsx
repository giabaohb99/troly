import { Browser } from '@capacitor/browser'
import { ExternalLink } from 'lucide-react'
import { isNative } from '@/core/config'
import { LONG_LINK_CHARS, linkHost, tokenizeText } from '@/shared/utils/text-tokens'

// Mở link ngoài bằng trình duyệt hệ thống (cả http, vì là link người khác gửi; không mở trong khung app).
export function openWebLink(href: string) {
  if (!/^https?:\/\//i.test(href)) return
  if (isNative) void Browser.open({ url: href })
  else window.open(href, '_blank', 'noopener,noreferrer')
}

interface RichTextProps {
  text: string
  // Link dài hơn 40 ký tự hiện gọn thành chip tên miền, bấm vẫn mở link thật (Hộp tin, thư; phản hồi 1.0.8).
  compactLinks?: boolean
  // Bấm email: mặc định mailto:; Hộp tin truyền vào để mở màn soạn thư của app.
  onEmail?: (email: string) => void
}

// Chữ tin nhắn: giữ xuống dòng, in đậm **...**, link bấm mở trình duyệt, số điện thoại bấm gọi, email bấm soạn thư.
export function RichText({ text, compactLinks = false, onEmail }: RichTextProps) {
  return (
    <>
      {tokenizeText(text).map((t, i) => {
        if (t.type === 'bold') return <strong key={i}>{t.value}</strong>
        if (t.type === 'link') {
          const open = (e: React.MouseEvent) => {
            e.preventDefault()
            e.stopPropagation()
            openWebLink(t.href)
          }
          if (compactLinks && t.value.length > LONG_LINK_CHARS)
            return (
              <a
                key={i}
                href={t.href}
                title={t.href}
                onClick={open}
                className="mx-0.5 inline-flex max-w-full items-center gap-1 rounded-full border bg-secondary px-2 py-0.5 align-middle text-xs font-medium text-primary no-underline"
              >
                <ExternalLink className="size-3 shrink-0" />
                <span className="truncate">{linkHost(t.href)}</span>
              </a>
            )
          return (
            <a key={i} href={t.href} onClick={open} className="break-all underline underline-offset-2">
              {t.value}
            </a>
          )
        }
        if (t.type === 'phone')
          return (
            <a key={i} href={t.href} onClick={(e) => e.stopPropagation()} className="underline underline-offset-2">
              {t.value}
            </a>
          )
        if (t.type === 'email')
          return (
            <a
              key={i}
              href={t.href}
              onClick={(e) => {
                e.stopPropagation()
                if (onEmail) {
                  e.preventDefault()
                  onEmail(t.value)
                }
              }}
              className="break-all underline underline-offset-2"
            >
              {t.value}
            </a>
          )
        return <span key={i}>{t.value}</span>
      })}
    </>
  )
}
