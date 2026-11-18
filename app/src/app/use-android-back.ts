import { useEffect } from 'react'
import { App } from '@capacitor/app'
import { useLocation, useNavigate } from 'react-router-dom'
import { isNative } from '@/core/config'

const ROOTS = ['/hop-tin', '/lich', '/chi-tieu', '/lich-trinh', '/bao-cao', '/cai-dat', '/tim', '/thiet-lap']

// Nút quay lại của Android (31 mục 3.2): hộp thoại Radix tự đóng bằng Escape; màn con về màn cha;
// màn gốc về Trợ lý; ở Trợ lý thì thu nhỏ app.
export function useAndroidBack() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  useEffect(() => {
    if (!isNative) return
    const handle = App.addListener('backButton', () => {
      const openDialog = document.querySelector('[role="dialog"], [role="alertdialog"]')
      if (openDialog) {
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
        return
      }
      if (pathname === '/' || pathname === '/dang-nhap') void App.minimizeApp()
      else if (ROOTS.includes(pathname)) navigate('/')
      else navigate(-1)
    })
    return () => {
      void handle.then((h) => h.remove())
    }
  }, [navigate, pathname])
}
