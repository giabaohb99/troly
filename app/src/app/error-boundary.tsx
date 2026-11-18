import { Component, type ErrorInfo, type ReactNode } from 'react'
import { RefreshCw, TriangleAlert } from 'lucide-react'
import { reportUiError } from '@/core/report-error'

interface ErrorBoundaryState {
  error: Error | null
}

// Không bao giờ màn trắng hay đen (QĐ-30): màn hỏng lúc chạy thì hiện câu lỗi và nút Tải lại, gửi lỗi về máy chủ.
export class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    reportUiError(Object.assign(error, { stack: `${error.stack ?? ''}\n${info.componentStack ?? ''}` }), 'render')
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="mx-auto flex min-h-[60dvh] max-w-sm flex-col items-center justify-center gap-4 px-6 text-center">
        <TriangleAlert className="size-10 text-warning" />
        <h1 className="text-lg font-semibold">Màn này đang lỗi</h1>
        <p className="text-sm text-muted-foreground">Lỗi đã được gửi về máy chủ. Bấm tải lại để mở lại app.</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 font-semibold text-primary-foreground"
        >
          <RefreshCw className="size-4" />
          Tải lại
        </button>
        <p className="text-xs break-all text-muted-foreground/70">{this.state.error.message}</p>
      </div>
    )
  }
}
