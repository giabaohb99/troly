import { registerPlugin, WebPlugin, type PluginListenerHandle } from '@capacitor/core'
import { apiGet } from '@/core/api/http-client'
import { getAppId, getAppVersion, isDebugBuild, isNative } from '@/core/config'

// Kiểm bản APK mới (12-api.md mục 5.8). V1 chỉ cập nhật bằng APK, luôn hỏi trước khi cài (QĐ-18, QĐ-27).
// Bấm Cập nhật (30 mục 3.11, sửa lỗi 1.0.9): lấy lại link ngay lúc bấm (link R2 ký sẵn chỉ sống 300 giây), tải bằng
// UpdatePlugin.kt trong app có tiến trình, kiểm sha256 và tên gói, rồi mở trình cài đặt của Android. Chưa được cài
// từ nguồn này thì mở đúng trang cài đặt đó, quay về thì cài tiếp.

export interface ReleaseInfo {
  update_available: boolean
  required: boolean
  latest: {
    version_code: number
    version_name: string
    // Link ký mới mỗi lần gọi, sống download_expires_in giây (1.800); vì vậy bấm tải là gọi lại.
    download_url: string
    download_expires_in?: number
    sha256: string
    size_bytes: number
    notes: string | null
    min_supported_version_code: number
    // Gói của APK; có thì chỉ nhận khi trùng gói đang chạy.
    package_name?: string | null
  } | null
}

// Trang tải công khai, dự phòng khi tải trong app không được (không dùng link ký vì hết hạn).
export const DOWNLOAD_PAGE_URL = 'https://assistant.baohuynh.io.vn/tai-app'

export interface UpdatePluginApi {
  download(options: { url: string; sha256: string; versionCode: number; size: number }): Promise<{ path: string; reused: boolean }>
  canInstall(): Promise<{ allowed: boolean }>
  openInstallSettings(): Promise<{ allowed: boolean }>
  install(options: { path: string }): Promise<void>
  cleanup(): Promise<void>
  openBrowser(options: { url: string }): Promise<void>
  addListener(event: 'progress', listener: (e: { done: number; total: number; percent: number }) => void): Promise<PluginListenerHandle>
}

class UpdateWeb extends WebPlugin {
  async download(): Promise<never> {
    throw this.unavailable('Chỉ cập nhật được trên app Android.')
  }
  async canInstall() {
    return { allowed: false }
  }
  async openInstallSettings() {
    return { allowed: false }
  }
  async install() {}
  async cleanup() {}
  async openBrowser({ url }: { url: string }) {
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

export const Update = registerPlugin<UpdatePluginApi>('Update', { web: () => new UpdateWeb() as unknown as UpdatePluginApi })

const NO_UPDATE: ReleaseInfo = { update_available: false, required: false, latest: null }

// Bản thử (gói .debug) không nhận bản chính thức: khác gói, bấm vào là cài thêm app khác chứ không cập nhật.
// Bản thử cập nhật bằng cách cài APK debug mới.
export async function checkRelease(): Promise<ReleaseInfo> {
  if (isDebugBuild()) return NO_UPDATE
  const release = await apiGet<ReleaseInfo>(`/device/release?current_version_code=${getAppVersion().code}`)
  const pkg = release.latest?.package_name
  if (isNative && pkg && pkg !== getAppId()) return NO_UPDATE
  // Không còn bản mới tức đã cài xong: bỏ tệp APK tải về lần trước.
  if (isNative && !release.update_available) void Update.cleanup().catch(() => undefined)
  return release
}

export const openDownloadPage = () => Update.openBrowser({ url: DOWNLOAD_PAGE_URL })

// Trên trình duyệt không có APK để cập nhật: không hiện dải báo bản mới.
export const canInstallApk = isNative

export type ApkUpdateState =
  | { step: 'idle' }
  | { step: 'checking' }
  // percent -1 khi chưa biết cỡ tệp.
  | { step: 'downloading'; percent: number }
  | { step: 'need_permission'; path: string }
  | { step: 'installing'; path: string }
  // Đã mở trình cài đặt; người dùng hủy hộp đó thì bấm Cài lại.
  | { step: 'ready'; path: string }
  | { step: 'error'; message: string; retry: boolean }

const ERRORS: Record<string, { message: string; retry: boolean }> = {
  network: { message: 'Mất mạng khi tải bản mới.', retry: true },
  http: { message: 'Link tải hết hạn hoặc máy chủ lỗi.', retry: true },
  sha: { message: 'Tệp tải về không khớp mã kiểm, đã xóa.', retry: true },
  package: { message: 'Tệp tải về không phải bản của Trợ lý, đã xóa.', retry: false },
  size: { message: 'Tệp tải về quá lớn, đã dừng.', retry: false },
  storage: { message: 'Máy không đủ chỗ trống để tải bản mới.', retry: true },
  settings: { message: 'Không mở được trình cài đặt của Android.', retry: true },
}

export function updateErrorState(error: unknown): ApkUpdateState {
  const code = (error as { code?: string } | null)?.code
  const known = code ? ERRORS[code] : undefined
  return { step: 'error', ...(known ?? { message: 'Chưa cập nhật được.', retry: true }) }
}

export interface UpdateDeps {
  fetchRelease: () => Promise<ReleaseInfo>
  plugin: Pick<UpdatePluginApi, 'download' | 'canInstall' | 'openInstallSettings' | 'install' | 'addListener'>
}

// Cả luồng bấm Cập nhật. Mỗi lần gọi lấy lại /device/release để có link ký mới.
export async function runApkUpdate(deps: UpdateDeps, set: (s: ApkUpdateState) => void): Promise<void> {
  set({ step: 'checking' })
  let release: ReleaseInfo
  try {
    release = await deps.fetchRelease()
  } catch {
    set({ step: 'error', message: 'Không lấy được bản mới, kiểm tra mạng.', retry: true })
    return
  }
  const latest = release.update_available ? release.latest : null
  if (!latest) {
    set({ step: 'error', message: 'Máy đã ở bản mới nhất.', retry: false })
    return
  }
  set({ step: 'downloading', percent: 0 })
  const handle = await deps.plugin.addListener('progress', (e) => set({ step: 'downloading', percent: e.percent }))
  let path: string
  try {
    path = (await deps.plugin.download({ url: latest.download_url, sha256: latest.sha256, versionCode: latest.version_code, size: latest.size_bytes })).path
  } catch (error) {
    set(updateErrorState(error))
    return
  } finally {
    void handle.remove()
  }
  await installDownloaded(deps.plugin, path, set)
}

// Mở trình cài đặt cho tệp đã tải; chưa được phép cài từ nguồn này thì mở trang cài đặt đó trước.
export async function installDownloaded(plugin: UpdateDeps['plugin'], path: string, set: (s: ApkUpdateState) => void): Promise<void> {
  try {
    let { allowed } = await plugin.canInstall()
    if (!allowed) {
      set({ step: 'need_permission', path })
      ;({ allowed } = await plugin.openInstallSettings())
      if (!allowed) return
    }
    set({ step: 'installing', path })
    await plugin.install({ path })
    set({ step: 'ready', path })
  } catch (error) {
    const code = (error as { code?: string } | null)?.code
    set(code === 'not_allowed' ? { step: 'need_permission', path } : updateErrorState(error))
  }
}
