import { Loader2 } from 'lucide-react'
import { Navigate, Outlet } from 'react-router-dom'
import { useSession } from '@/modules/auth/hooks/use-session'
import { ErrorState } from '@/shared/components/error-state'

export function RequireAuth() {
  const { data, isPending, isError, error, refetch } = useSession()
  if (isPending) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-muted-foreground">
        <Loader2 className="size-6 animate-spin" />
      </div>
    )
  }
  // Lỗi mạng khi mở app: không đẩy về màn đăng nhập, cho thử lại.
  if (isError) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-sm items-center px-6">
        <ErrorState error={error} onRetry={() => void refetch()} />
      </div>
    )
  }
  if (!data) return <Navigate to="/dang-nhap" replace />
  return <Outlet />
}
