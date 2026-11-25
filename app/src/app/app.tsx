import { useEffect } from 'react'
import { App as CapApp } from '@capacitor/app'
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { ApiError } from '@/core/api/api-error'
import { AppLayout } from '@/app/app-layout'
import { ErrorBoundary } from '@/app/error-boundary'
import { lazyPage } from '@/app/lazy-page'
import { ShareIn } from '@/core/native/share-in'
import { openSessionPath } from '@/modules/chat/utils/sessions'
import { FeatureGate } from '@/shared/components/feature-gate'
import { useAndroidBack } from '@/app/use-android-back'
import { RequireAuth } from '@/modules/auth/components/require-auth'
import { LoginPage } from '@/modules/auth/pages/login-page'
import { ChatPage } from '@/modules/chat/pages/chat-page'
import { queryKeys } from '@/shared/constants/query-keys'
import { Toaster } from '@/shared/ui/sonner'
import { deepLinkToRoute } from '@/shared/utils/deep-link'

const ExpensePage = lazyPage(() => import('@/modules/expense/pages/expense-page').then((m) => m.ExpensePage))
const SearchPage = lazyPage(() => import('@/modules/search/pages/search-page').then((m) => m.SearchPage))
const SettingsPage = lazyPage(() => import('@/modules/setting/pages/settings-page').then((m) => m.SettingsPage))
const InboxPage = lazyPage(() => import('@/modules/inbox/pages/inbox-page').then((m) => m.InboxPage))
const ZaloSettingsPage = lazyPage(() => import('@/modules/setting/pages/zalo-settings-page').then((m) => m.ZaloSettingsPage))
const ZaloChatPage = lazyPage(() => import('@/modules/inbox/pages/zalo-chat-page').then((m) => m.ZaloChatPage))
const ZaloNewPage = lazyPage(() => import('@/modules/inbox/pages/zalo-new-page').then((m) => m.ZaloNewPage))
const ConnectorsPage = lazyPage(() => import('@/modules/setting/pages/connectors-page').then((m) => m.ConnectorsPage))
const ConnectorPage = lazyPage(() => import('@/modules/setting/pages/connector-page').then((m) => m.ConnectorPage))
const MarkdownPage = lazyPage(() => import('@/modules/file/pages/markdown-page').then((m) => m.MarkdownPage))
const EmailThreadPage = lazyPage(() => import('@/modules/inbox/pages/email-thread-page').then((m) => m.EmailThreadPage))
const EmailComposePage = lazyPage(() => import('@/modules/inbox/pages/email-compose-page').then((m) => m.EmailComposePage))
const ConversationPage = lazyPage(() => import('@/modules/inbox/pages/conversation-page').then((m) => m.ConversationPage))
const DeviceSetupPage = lazyPage(() => import('@/modules/device/pages/device-setup-page').then((m) => m.DeviceSetupPage))
const CalendarPage = lazyPage(() => import('@/modules/calendar/pages/calendar-page').then((m) => m.CalendarPage))
const GooglePage = lazyPage(() => import('@/modules/setting/pages/google-page').then((m) => m.GooglePage))
const AiCostPage = lazyPage(() => import('@/modules/setting/pages/ai-cost-page').then((m) => m.AiCostPage))
const InboxSettingsPage = lazyPage(() => import('@/modules/setting/pages/inbox-settings-page').then((m) => m.InboxSettingsPage))
const NotifySettingsPage = lazyPage(() => import('@/modules/setting/pages/notify-settings-page').then((m) => m.NotifySettingsPage))
const TripSettingsPage = lazyPage(() => import('@/modules/setting/pages/trip-settings-page').then((m) => m.TripSettingsPage))
const TripListPage = lazyPage(() => import('@/modules/trip/pages/trip-list-page').then((m) => m.TripListPage))
const TripPage = lazyPage(() => import('@/modules/trip/pages/trip-page').then((m) => m.TripPage))
const ReportPage = lazyPage(() => import('@/modules/report/pages/report-page').then((m) => m.ReportPage))

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

// Đường dẫn sâu troly://<đường dẫn> (thông báo nhắc, trang kết nối Google, thông báo trợ lý trả lời).
function DeepLinks() {
  const navigate = useNavigate()
  useAndroidBack()
  // Chia sẻ từ app khác vào Trợ lý (QĐ-51 bước 2): vào ô nhập của khung chat đang mở (hoặc mở gần nhất).
  useEffect(() => {
    const handle = ShareIn.addListener('shared', (payload) => navigate(openSessionPath(), { state: { shared: payload } }))
    return () => {
      void handle.then((h) => h.remove())
    }
  }, [navigate])
  useEffect(() => {
    const handle = CapApp.addListener('appUrlOpen', ({ url }) => {
      const match = url.match(/^troly:\/\/(.*)$/)
      if (match) navigate(deepLinkToRoute(match[1]))
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
                <Route path="xem-tep/:fileId" element={<MarkdownPage />} />
                <Route path="hop-tin/email/soan" element={<EmailComposePage />} />
                <Route path="hop-tin/email/:threadId" element={<EmailThreadPage />} />
                <Route path="hop-tin/:conversationKey" element={<ConversationPage />} />
                <Route path="thiet-lap" element={<DeviceSetupPage />} />
                <Route path="cai-dat/google" element={<GooglePage />} />
                <Route path="lich" element={<CalendarPage />} />
                <Route path="lich/su-kien/:eventId" element={<CalendarPage />} />
                <Route path="lich/viec/:taskId" element={<CalendarPage />} />
                <Route path="cai-dat/chi-phi" element={<AiCostPage />} />
                <Route path="cai-dat/hop-tin" element={<InboxSettingsPage />} />
                <Route path="cai-dat/thong-bao" element={<NotifySettingsPage />} />
                <Route path="cai-dat/lich-trinh" element={<TripSettingsPage />} />
                {/* Zalo đầy đủ qua bridge (QĐ-52) chỉ khi cờ zalo_bridge bật. */}
                <Route path="cai-dat/zalo" element={<FeatureGate flag="zalo_bridge"><ZaloSettingsPage /></FeatureGate>} />
                <Route path="zalo/moi" element={<FeatureGate flag="zalo_bridge" fallback="/hop-tin"><ZaloNewPage /></FeatureGate>} />
                <Route path="zalo/:conversationKey" element={<FeatureGate flag="zalo_bridge" fallback="/hop-tin"><ZaloChatPage /></FeatureGate>} />
                {/* Kết nối (QĐ-56) chỉ mở khi máy chủ bật cờ connectors. */}
                <Route path="cai-dat/ket-noi" element={<FeatureGate flag="connectors"><ConnectorsPage /></FeatureGate>} />
                <Route path="cai-dat/ket-noi/:connectorId" element={<FeatureGate flag="connectors"><ConnectorPage /></FeatureGate>} />
                <Route path="lich-trinh" element={<TripListPage />} />
                <Route path="lich-trinh/:tripId" element={<TripPage />} />
                <Route path="bao-cao" element={<ReportPage />} />
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
