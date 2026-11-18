import { registerPlugin, WebPlugin } from '@capacitor/core'

// Mở tệp bot xuất (QĐ-41). Trên Android: FilesPlugin.kt tải về bộ nhớ đệm rồi mở bằng trình xem của máy.
// Trên trình duyệt: mở link tải ở thẻ mới.

export interface FilesPlugin {
  open(options: { url: string; name: string; mime: string }): Promise<{ opened: boolean; path: string | null }>
  share(options: { path: string; mime: string }): Promise<void>
}

class FilesWeb extends WebPlugin {
  async open({ url }: { url: string; name: string; mime: string }) {
    window.open(url, '_blank', 'noopener,noreferrer')
    return { opened: true, path: null }
  }

  async share() {}
}

export const Files = registerPlugin<FilesPlugin>('Files', { web: () => new FilesWeb() })
