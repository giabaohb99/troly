import { Browser } from '@capacitor/browser'
import { isNative } from '@/core/config'

// Link ngoài luôn mở bằng trình duyệt hệ thống, không mở trong khung app (30 mục 3.2). Chỉ nhận https.
export async function openExternal(url: string): Promise<boolean> {
  if (!/^https:\/\//i.test(url)) return false
  if (isNative) await Browser.open({ url })
  else window.open(url, '_blank', 'noopener,noreferrer')
  return true
}
