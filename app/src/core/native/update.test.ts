import { describe, expect, it, vi } from 'vitest'
import { runApkUpdate, updateErrorState, type ApkUpdateState, type ReleaseInfo, type UpdateDeps } from '@/core/native/update'

const release = (url: string): ReleaseInfo => ({
  update_available: true,
  required: false,
  latest: { version_code: 110, version_name: '1.1.0', download_url: url, sha256: 'a'.repeat(64), size_bytes: 100, notes: null, min_supported_version_code: 1 },
})

function fakePlugin(over: Partial<UpdateDeps['plugin']> = {}) {
  let progress: ((e: { done: number; total: number; percent: number }) => void) | undefined
  const plugin: UpdateDeps['plugin'] = {
    addListener: vi.fn(async (_e, l) => {
      progress = l
      return { remove: async () => undefined }
    }) as UpdateDeps['plugin']['addListener'],
    download: vi.fn(async () => {
      progress?.({ done: 50, total: 100, percent: 50 })
      return { path: '/data/files/updates/troly-110.apk', reused: false }
    }),
    canInstall: vi.fn(async () => ({ allowed: true })),
    openInstallSettings: vi.fn(async () => ({ allowed: true })),
    install: vi.fn(async () => undefined),
    ...over,
  }
  return plugin
}

async function run(deps: UpdateDeps) {
  const states: ApkUpdateState[] = []
  await runApkUpdate(deps, (s) => states.push(s))
  return states
}

describe('cập nhật APK trong app', () => {
  it('lấy link mới lúc bấm, tải có phần trăm, kiểm xong mở trình cài', async () => {
    const fetchRelease = vi.fn(async () => release('https://r2/ky-moi'))
    const plugin = fakePlugin()
    const states = await run({ fetchRelease, plugin })
    expect(fetchRelease).toHaveBeenCalledTimes(1)
    expect(plugin.download).toHaveBeenCalledWith({ url: 'https://r2/ky-moi', sha256: 'a'.repeat(64), versionCode: 110, size: 100 })
    expect(states.map((s) => s.step)).toEqual(['checking', 'downloading', 'downloading', 'installing', 'ready'])
    expect(states[2]).toEqual({ step: 'downloading', percent: 50 })
    expect(plugin.install).toHaveBeenCalledWith({ path: '/data/files/updates/troly-110.apk' })
  })

  it('chưa cho cài từ nguồn này: mở trang cài đặt, quay về đã bật thì cài tiếp', async () => {
    const plugin = fakePlugin({ canInstall: vi.fn(async () => ({ allowed: false })) })
    const states = await run({ fetchRelease: async () => release('https://r2/x'), plugin })
    expect(plugin.openInstallSettings).toHaveBeenCalled()
    expect(states.map((s) => s.step)).toContain('need_permission')
    expect(states.at(-1)?.step).toBe('ready')
  })

  it('quay về mà chưa bật: dừng ở bước xin quyền, không cài', async () => {
    const plugin = fakePlugin({ canInstall: vi.fn(async () => ({ allowed: false })), openInstallSettings: vi.fn(async () => ({ allowed: false })) })
    const states = await run({ fetchRelease: async () => release('https://r2/x'), plugin })
    expect(states.at(-1)).toEqual({ step: 'need_permission', path: '/data/files/updates/troly-110.apk' })
    expect(plugin.install).not.toHaveBeenCalled()
  })

  it('lỗi mạng, sai mã kiểm, sai gói: báo câu tiếng Việt, cho thử lại khi hợp lý', async () => {
    const fail = (code: string) => fakePlugin({ download: vi.fn(async () => Promise.reject(Object.assign(new Error('x'), { code }))) })
    expect((await run({ fetchRelease: async () => release('https://r2/x'), plugin: fail('network') })).at(-1)).toEqual({ step: 'error', message: 'Mất mạng khi tải bản mới.', retry: true })
    expect((await run({ fetchRelease: async () => release('https://r2/x'), plugin: fail('sha') })).at(-1)).toMatchObject({ step: 'error', retry: true })
    expect((await run({ fetchRelease: async () => release('https://r2/x'), plugin: fail('package') })).at(-1)).toMatchObject({ step: 'error', retry: false })
    expect(updateErrorState(new Error('la'))).toEqual({ step: 'error', message: 'Chưa cập nhật được.', retry: true })
  })

  it('không lấy được link hoặc đã ở bản mới: không tải', async () => {
    const plugin = fakePlugin()
    expect((await run({ fetchRelease: () => Promise.reject(new Error('mạng')), plugin })).at(-1)).toMatchObject({ step: 'error', retry: true })
    expect((await run({ fetchRelease: async () => ({ update_available: false, required: false, latest: null }), plugin })).at(-1)).toMatchObject({ step: 'error', retry: false })
    expect(plugin.download).not.toHaveBeenCalled()
  })
})
