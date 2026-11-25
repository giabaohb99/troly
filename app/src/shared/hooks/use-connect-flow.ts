import { Browser } from '@capacitor/browser'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { getErrorMessage } from '@/core/api/api-error'
import { isNative } from '@/core/config'
import { startConnect } from '@/shared/api/connectors-api'

// Luồng đăng nhập một kết nối (QĐ-56): máy chủ trả trang đăng nhập của hệ thống, mở trong trình duyệt của app (như
// Google); người dùng nhập mật khẩu, bấm đồng ý trên trang đó, rồi về app bằng troly://settings/connectors?ok=1&id=.
// Dùng ở Cài đặt → Kết nối và nút Kết nối trợ lý gửi trong chat.
export function useConnectFlow() {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: (id: number) => startConnect(id),
    onSuccess: async ({ auth_url }) => {
      if (isNative) await Browser.open({ url: auth_url })
      else if (auth_url.startsWith('/')) navigate(auth_url)
      else window.location.assign(auth_url)
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })
}
