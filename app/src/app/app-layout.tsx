import { Suspense, useState } from 'react'
import { CalendarDays, ChartColumn, Inbox, LayoutGrid, Loader2, MessageCircle, Route, Settings, Wallet } from 'lucide-react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { ErrorBoundary } from '@/app/error-boundary'
import { useDeviceStartup } from '@/app/use-device-startup'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/ui/dialog'
import { cn } from '@/shared/utils/cn'

// Thanh dưới 5 ô (31 mục 3.2): Trợ lý, Hộp tin, Lịch, Chi tiêu, Thêm.
const NAV_ITEMS = [
  { to: '/', label: 'Trợ lý', icon: MessageCircle },
  { to: '/hop-tin', label: 'Hộp tin', icon: Inbox },
  { to: '/lich', label: 'Lịch', icon: CalendarDays },
  { to: '/chi-tieu', label: 'Chi tiêu', icon: Wallet },
]

const MORE_ITEMS = [
  { to: '/lich-trinh', label: 'Lịch trình', icon: Route },
  { to: '/bao-cao', label: 'Báo cáo', icon: ChartColumn },
  { to: '/cai-dat', label: 'Cài đặt', icon: Settings },
]

const navClass = (active: boolean) =>
  cn('flex w-full flex-col items-center gap-1 py-2.5 text-[11px] font-medium text-muted-foreground transition-colors', active && 'text-primary')

export function AppLayout() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [moreOpen, setMoreOpen] = useState(false)
  useDeviceStartup()
  const moreActive = MORE_ITEMS.some((item) => pathname.startsWith(item.to))

  return (
    <div className="mx-auto flex min-h-dvh max-w-lg flex-col">
      <main className="flex-1 px-4 pt-[max(env(safe-area-inset-top),1rem)] pb-28">
        <Suspense
          fallback={
            <div className="flex justify-center py-16 text-muted-foreground">
              <Loader2 className="size-6 animate-spin" />
            </div>
          }
        >
          <ErrorBoundary key={pathname}>
            <Outlet />
          </ErrorBoundary>
        </Suspense>
      </main>
      <nav className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur">
        <ul className="mx-auto grid max-w-lg grid-cols-5">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink to={to} end={to === '/'} className={({ isActive }) => navClass(isActive)}>
                <Icon className="size-5" />
                {label}
              </NavLink>
            </li>
          ))}
          <li>
            <button type="button" className={navClass(moreActive)} onClick={() => setMoreOpen(true)}>
              <LayoutGrid className="size-5" />
              Thêm
            </button>
          </li>
        </ul>
      </nav>
      <Dialog open={moreOpen} onOpenChange={setMoreOpen}>
        <DialogContent className="top-auto bottom-[calc(4.5rem+env(safe-area-inset-bottom))] translate-y-0">
          <DialogHeader>
            <DialogTitle>Thêm</DialogTitle>
            <DialogDescription className="sr-only">Các màn ít dùng</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-3 gap-2">
            {MORE_ITEMS.map(({ to, label, icon: Icon }) => (
              <button
                key={to}
                type="button"
                onClick={() => {
                  setMoreOpen(false)
                  navigate(to)
                }}
                className={cn('flex flex-col items-center gap-2 rounded-xl bg-secondary px-2 py-4 text-sm', pathname.startsWith(to) && 'text-primary')}
              >
                <Icon className="size-6" />
                {label}
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
