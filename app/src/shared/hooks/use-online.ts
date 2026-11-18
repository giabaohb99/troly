import { useEffect, useState } from 'react'
import { Network } from '@capacitor/network'

// Trạng thái mạng: plugin Network chạy được cả trên Android lẫn trình duyệt.
export function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine)
  useEffect(() => {
    let cancelled = false
    void Network.getStatus().then((status) => {
      if (!cancelled) setOnline(status.connected)
    })
    const handle = Network.addListener('networkStatusChange', (status) => setOnline(status.connected))
    return () => {
      cancelled = true
      void handle.then((h) => h.remove())
    }
  }, [])
  return online
}
