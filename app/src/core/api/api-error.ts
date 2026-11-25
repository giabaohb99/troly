// Lỗi gọi API, mang câu báo lỗi tiếng Việt và mã lỗi máy chủ (`data.code`, 12-api.md mục 3.5).
export class ApiError extends Error {
  status: number
  code: string
  requestId: string | null
  fields: Record<string, string> | null
  // 429: số giây nên chờ (data.retry_after hoặc header Retry-After), null nếu máy chủ không nói.
  retryAfter: number | null = null

  constructor(status: number, message: string, code = 'UNKNOWN', requestId: string | null = null, fields: Record<string, string> | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
    this.fields = fields
  }
}

export const NETWORK_ERROR_MESSAGE = 'Không kết nối được máy chủ, kiểm tra mạng rồi thử lại.'

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return 'Có lỗi xảy ra, thử lại sau.'
}
