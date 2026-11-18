import { useEffect } from 'react'
import { App } from '@capacitor/app'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { isNative } from '@/core/config'
import { Alarm } from '@/core/native/alarm'
import { Notify } from '@/core/native/notify'
import { queryKeys } from '@/shared/constants/query-keys'

const SETUP_SEEN_KEY = 'troly.setup.seen'

// Trên điện thoại, sau khi đăng nhập: nhịp tim, tải danh sách app được nghe, gửi hàng đợi, tải lại nhắc; mỗi lần
// quay lại app thì gửi ngay hàng đợi (Doze có thể đã giữ lại) và tải lại nhắc (30 mục 3.9). Lần đầu thì mở màn
// Thiết lập máy (31 luồng 1).
export function useDeviceStartup() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  useEffect(() => {
    if (!isNative) return
    void Notify.sync()
    void Alarm.sync()
    if (!localStorage.getItem(SETUP_SEEN_KEY)) {
      localStorage.setItem(SETUP_SEEN_KEY, '1')
      navigate('/thiet-lap')
    }
    const handle = App.addListener('appStateChange', ({ isActive }) => {
      if (!isActive) return
      void Notify.flushQueue()
      void Alarm.sync()
    })
    // Bấm Xong, Đã biết, Hoãn trên thông báo nhắc khi app đang mở: tải lại màn Lịch.
    const reminder = Alarm.addListener('reminderAction', () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all })
    })
    return () => {
      void handle.then((h) => h.remove())
      void reminder.then((h) => h.remove())
    }
  }, [navigate, queryClient])
}
