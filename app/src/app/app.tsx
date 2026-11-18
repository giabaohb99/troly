import { useEffect } from 'react'
import { App as CapApp } from '@capacitor/app'
import { ChartColumn, Route as RouteIcon } from 'lucide-react'
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { ApiError } from '@/core/api/api-error'
import { AppLayout } from '@/app/app-layout'
import { ErrorBoundary } from '@/app/error-boundary'
import { lazyPage } from '@/app/lazy-page'
import { useAndroidBack } from '@/app/use-android-back'
import { RequireAuth } from '@/modules/auth/components/require-auth'
import { LoginPage } from '@/modules/auth/pages/login-page'
import { ChatPage } from '@/modules/chat/pages/chat-page'
import { queryKeys } from '@/shared/constants/query-keys'
import { ComingSoon } from '@/shared/components/coming-soon'
import { Toaster } from '@/shared/ui/sonner'

const ExpensePage = lazyPage(() => import('@/modules/expense/pages/expense-page').then((m) => m.ExpensePage))
const SearchPage = lazyPage(() => import('@/modules/search/pages/search-page').then((m) => m.SearchPage))
const SettingsPage = lazyPage(() => import('@/modules/setting/pages/settings-page').then((m) => m.SettingsPage))
const InboxPage = lazyPage(() => import('@/modules/inbox/pages/inbox-page').then((m) => m.InboxPage))
const ConversationPage = lazyPage(() => import('@/modules/inbox/pages/conversation-page').then((m) => m.ConversationPage))
const DeviceSetupPage = lazyPage(() => import('@/modules/device/pages/device-setup-page').then((m) => m.DeviceSetupPage))
const CalendarPage = lazyPage(() => import('@/modules/calendar/pages/calendar-page').then((m) => m.CalendarPage))
const GooglePage = lazyPage(() => import('@/modules/setting/pages/google-page').then((m) => m.GooglePage))

const isAuthError = (error: unknown) => error instanceof ApiError && error.status === 401

const queryClient: QueryClient = new QueryClient({
  // Phiên hỏng (401 sau khi đã thử làm mới): hỏi lại phiên để RequireAuth đưa về màn đăng nhập.
  queryCache: new QueryCache({
    onError: (error, query) => {
      if (isAuthError(error) && query.queryKey[0] !== 'auth') void queryClient.invalidateQueries({ queryKey: queryKeys.auth.me })
    },
  }),
  mutationCache: new MutationCache({
    onError: (error) => {
      if (isAuthError(error)) void queryClient.invalidateQueries({ queryKey: queryKeys.auth.me })
    },
  }),
  defaultOptions: {
    queries: {
      retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
      refetchOnWindowFocus: true,
    },
  },
})

// Đường dẫn sâu troly://<đường dẫn> (thông báo nhắc, trang kết nối Google).
function DeepLinks() {
  const navigate = useNavigate()
  useAndroidBack()
  useEffect(() => {
    const handle = CapApp.addListener('appUrlOpen', ({ url }) => {
      const match = url.match(/^troly:\/\/(.*)$/)
      if (match) navigate(`/${match[1]}`)
    })
    return () => {
      void handle.then((h) => h.remove())
    }
  }, [navigate])
  return null
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary>
          <DeepLinks />
          <Routes>
            <Route path="/dang-nhap" element={<LoginPage />} />
            <Route element={<RequireAuth />}>
              <Route element={<AppLayout />}>
                <Route index element={<ChatPage />} />
                <Route path="tim" element={<SearchPage />} />
                <Route path="chi-tieu" element={<ExpensePage />} />
                <Route path="cai-dat" element={<SettingsPage />} />
                <Route path="hop-tin" element={<InboxPage />} />
                <Route path="hop-tin/:conversationKey" element={<ConversationPage />} />
                <Route path="thiet-lap" element={<DeviceSetupPage />} />
                <Route path="cai-dat/google" element={<GooglePage />} />
                <Route path="lich" element={<CalendarPage />} />
                <Route path="lich/su-kien/:eventId" element={<CalendarPage />} />
                <Route path="lich/viec/:taskId" element={<CalendarPage />} />
                <Route path="lich-trinh" element={<ComingSoon title="Lịch trình" icon={RouteIcon} phase={4} text="Nhập lịch trình, đánh giá rủi ro và mở Google Maps." />} />
                <Route path="bao-cao" element={<ComingSoon title="Báo cáo" icon={ChartColumn} phase={4} text="Bảng số liệu chi tiêu, lịch, hộp tin, chi phí AI." />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ErrorBoundary>
      </BrowserRouter>
      <Toaster />
    </QueryClientProvider>
  )
}
