import { registerPlugin, WebPlugin } from '@capacitor/core'

// Mở Google Maps (30 mục 3.12). Trên Android: MapsPlugin.kt; trên trình duyệt: mở tab mới bằng link https.

export interface NavigateOptions {
  lat: number | null
  lng: number | null
  query: string | null
  // `l` xe hai bánh, `d` ô tô, `w` đi bộ; `avoid: 'h'` tránh cao tốc.
  mode: string
  avoid: string | null
  // Lệnh google.navigation: dựng sẵn ở máy chủ (QĐ-36); có thì mở thẳng.
  uri?: string | null
  fallbackUrl?: string | null
}

export interface MapsPlugin {
  navigate(options: NavigateOptions): Promise<{ opened: 'maps' | 'browser' }>
  openUrl(options: { url: string }): Promise<{ opened: 'maps' | 'browser' }>
  isMapsInstalled(): Promise<{ value: boolean }>
}

class MapsWeb extends WebPlugin {
  async navigate(options: NavigateOptions) {
    const target = options.lat !== null && options.lng !== null ? `${options.lat},${options.lng}` : encodeURIComponent(options.query ?? '')
    const url = options.fallbackUrl ?? `https://www.google.com/maps/dir/?api=1&destination=${target}&travelmode=two-wheeler&dir_action=navigate`
    window.open(url, '_blank', 'noopener,noreferrer')
    return { opened: 'browser' as const }
  }

  async openUrl({ url }: { url: string }) {
    if (!url.startsWith('https://')) throw new Error('Link không an toàn.')
    window.open(url, '_blank', 'noopener,noreferrer')
    return { opened: 'browser' as const }
  }

  // Trình duyệt coi như không có app Maps: link chỉ đường giới hạn 3 điểm dừng.
  async isMapsInstalled() {
    return { value: false }
  }
}

export const Maps = registerPlugin<MapsPlugin>('Maps', { web: () => new MapsWeb() })

export function placeUrl(query: string, placeId: string | null): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}${placeId ? `&query_place_id=${encodeURIComponent(placeId)}` : ''}`
}

// Số điểm dừng tối đa trong một link chỉ đường: 9 khi có app Maps, 3 khi chỉ có trình duyệt (41 mục 7).
export async function maxWaypoints(): Promise<9 | 3> {
  const { value } = await Maps.isMapsInstalled().catch(() => ({ value: false }))
  return value ? 9 : 3
}
