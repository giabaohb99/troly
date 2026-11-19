import { Browser } from '@capacitor/browser'
import { isNative } from '@/core/config'
import { tokenizeText } from '@/shared/utils/text-tokens'

// Mở link ngoài bằng trình duyệt hệ thống (cả http, vì là link người khác gửi; không mở trong khung app).
export function openWebLink(href: string) {
  if (!/^https?:\/\//i.test(href)) return
  if (isNative) void Browser.open({ url: href })
  else window.open(href, '_blank', 'noopener,noreferrer')
}

// Chữ tin nhắn: giữ xuống dòng, in đậm **...**, link bấm mở trình duyệt, số điện thoại bấm gọi (QĐ-44).
export function RichText({ text }: { text: string }) {
  return (
    <>
      {tokenizeText(text).map((t, i) => {
        if (t.type === 'bold') return <strong key={i}>{t.value}</strong>
        if (t.type === 'link')
          return (
            <a
              key={i}
              href={t.href}
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                openWebLink(t.href)
              }}
              className="break-all underline underline-offset-2"
            >
              {t.value}
            </a>
          )
        if (t.type === 'phone')
          return (
            <a key={i} href={t.href} onClick={(e) => e.stopPropagation()} className="underline underline-offset-2">
              {t.value}
            </a>
          )
        return <span key={i}>{t.value}</span>
      })}
    </>
  )
}
