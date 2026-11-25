import { Capacitor, registerPlugin, WebPlugin, type PluginListenerHandle } from '@capacitor/core'

// Chia sẻ từ app khác vào Trợ lý (QĐ-51 bước 2). Trên Android: ShareInPlugin.kt nhận ACTION_SEND, chép tệp vào bộ
// nhớ đệm rồi báo sự kiện `shared`. Trên trình duyệt: window.__trolyShare({...}) giả một lần chia sẻ để thử màn.

export interface SharedFile {
  // Đường dẫn tệp trong bộ nhớ đệm của app (trình duyệt: link blob: hoặc data:).
  path: string
  name: string
  mime: string
  size: number
}

export interface SharedPayload {
  text: string | null
  files: SharedFile[]
  // Số tệp bỏ qua: loại không nhận, quá 25 MB, hoặc quá 4 tệp.
  skipped: number
}

export interface ShareInPlugin {
  cleanup(): Promise<void>
  addListener(event: 'shared', listener: (payload: SharedPayload) => void): Promise<PluginListenerHandle>
}

class ShareInWeb extends WebPlugin {
  constructor() {
    super()
    if (typeof window !== 'undefined') {
      ;(window as unknown as { __trolyShare: (p: Partial<SharedPayload>) => void }).__trolyShare = (p) =>
        this.notifyListeners('shared', { text: p.text ?? null, files: p.files ?? [], skipped: p.skipped ?? 0 }, true)
    }
  }

  async cleanup() {}
}

export const ShareIn = registerPlugin<ShareInPlugin>('ShareIn', { web: () => new ShareInWeb() as unknown as ShareInPlugin })

// Link đọc được tệp đã chép (Android: http://localhost/_capacitor_file_/...).
export function sharedFileUrl(file: SharedFile): string {
  if (/^(blob:|data:|https?:)/.test(file.path)) return file.path
  return Capacitor.convertFileSrc(file.path.startsWith('file://') ? file.path : `file://${file.path}`)
}

export async function sharedFileToFile(file: SharedFile): Promise<File> {
  const blob = await fetch(sharedFileUrl(file)).then((r) => {
    if (!r.ok) throw new Error('Không đọc được tệp chia sẻ.')
    return r.blob()
  })
  return new File([blob], file.name, { type: file.mime || blob.type })
}
