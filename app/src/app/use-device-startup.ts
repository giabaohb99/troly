import { useEffect } from 'react'
import { App } from '@capacitor/app'
import { useNavigate } from 'react-router-dom'
import { isNative } from '@/core/config'
import { Notify } from '@/core/native/notify'

const SETUP_SEEN_KEY = 'troly.setup.seen'

// Trên điện thoại, sau khi đăng nhập: nhịp tim, tải danh sách app được nghe, gửi hàng đợi; mỗi lần quay lại
// app thì gửi ngay hàng đợi (Doze có thể đã giữ lại). Lần đầu thì mở màn Thiết lập máy (31 luồng 1).
export function useDeviceStartup() {
  const navigate = useNavigate()
  useEffect(() => {
    if (!isNative) return
    void Notify.sync()
    if (!localStorage.getItem(SETUP_SEEN_KEY)) {
      localStorage.setItem(SETUP_SEEN_KEY, '1')
      navigate('/thiet-lap')
    }
    const handle = App.addListener('appStateChange', ({ isActive }) => {
      if (isActive) void Notify.flushQueue()
    })
    return () => {
      void handle.then((h) => h.remove())
    }
  }, [navigate])
}
