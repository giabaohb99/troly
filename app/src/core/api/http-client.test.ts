import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { ApiError } from '@/core/api/api-error'
import { apiGet } from '@/core/api/http-client'
import { clearSession, getAccessToken, saveTokens } from '@/core/auth/session'

let refreshCalls = 0
let validToken = 'access-2'

const server = setupServer(
  http.post('/api/v1/auth/refresh', async ({ request }) => {
    refreshCalls += 1
    const body = (await request.json()) as { refresh_token: string }
    if (body.refresh_token !== 'rt-1') return HttpResponse.json({ success: false, message: 'Hết phiên.', data: { code: 'AUTH_REFRESH_INVALID' } }, { status: 401 })
    return HttpResponse.json({
      success: true,
      message: '',
      data: { access_token: validToken, access_expires_at: new Date(Date.now() + 1_800_000).toISOString(), refresh_token: 'rt-1', refresh_expires_at: '2027-11-18T00:00:00+07:00', user: {} },
    })
  }),
  http.get('/api/v1/auth/me', ({ request }) => {
    if (request.headers.get('Authorization') !== `Bearer ${validToken}`) {
      return HttpResponse.json({ success: false, message: 'Mã hết hạn.', data: { code: 'AUTH_TOKEN_EXPIRED' } }, { status: 401 })
    }
    return HttpResponse.json({ success: true, message: '', data: { id: 1 } })
  }),
  http.get('/api/v1/broken', () => HttpResponse.json({ success: false, message: 'Dữ liệu chưa hợp lệ.', data: { code: 'VALIDATION_ERROR', fields: { q: 'Thiếu q.' } } }, { status: 400 })),
  http.post('/api/v1/client-logs', () => HttpResponse.json({ success: true, message: '', data: { accepted: 1 } })),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterAll(() => server.close())
afterEach(() => server.resetHandlers())
beforeEach(async () => {
  refreshCalls = 0
  validToken = 'access-2'
  await clearSession()
})

async function startWithStaleToken() {
  // Mã truy cập cũ còn "hạn" theo máy nhưng máy chủ đã coi là hết hạn.
  await saveTokens({ access_token: 'access-1', access_expires_at: new Date(Date.now() + 1_800_000).toISOString(), refresh_token: 'rt-1', refresh_expires_at: '2027-11-18T00:00:00+07:00' })
}

describe('http-client', () => {
  it('401 AUTH_TOKEN_EXPIRED thì làm mới một lần rồi gọi lại', async () => {
    await startWithStaleToken()
    await expect(apiGet('/auth/me')).resolves.toEqual({ id: 1 })
    expect(refreshCalls).toBe(1)
    expect(getAccessToken()).toBe('access-2')
  })

  it('nhiều yêu cầu cùng lúc chỉ làm mới một lần', async () => {
    await saveTokens({ access_token: 'x', access_expires_at: new Date(Date.now() - 1000).toISOString(), refresh_token: 'rt-1', refresh_expires_at: '2027-11-18T00:00:00+07:00' })
    await Promise.all([apiGet('/auth/me'), apiGet('/auth/me'), apiGet('/auth/me')])
    expect(refreshCalls).toBe(1)
  })

  it('mã làm mới hỏng thì xóa phiên và ném 401', async () => {
    await saveTokens({ access_token: 'x', access_expires_at: new Date(Date.now() - 1000).toISOString(), refresh_token: 'rt-sai', refresh_expires_at: '2027-11-18T00:00:00+07:00' })
    await expect(apiGet('/auth/me')).rejects.toMatchObject({ status: 401 })
    expect(getAccessToken()).toBeNull()
  })

  it('lỗi phong bì thành ApiError có mã và trường', async () => {
    await startWithStaleToken()
    validToken = 'access-1'
    const error = await apiGet('/broken').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 400, code: 'VALIDATION_ERROR', message: 'Dữ liệu chưa hợp lệ.', fields: { q: 'Thiếu q.' } })
  })
})
