import { apiGet } from '@/core/api/http-client'
import { getAppId, getAppVersion, isDebugBuild, isNative } from '@/core/config'
import { openExternal } from '@/core/native/open-external'

// Kiểm bản APK mới (12-api.md mục 5.8). V1 chỉ cập nhật bằng APK, luôn hỏi trước khi cài (QĐ-18, QĐ-27).
// Phase 1: bấm Cập nhật thì mở link tải trong trình duyệt hệ thống, Android tự hỏi cài. Cài bằng
// PackageInstaller trong app làm sau (30 mục 3.11).

export interface ReleaseInfo {
  update_available: boolean
  required: boolean
  latest: {
    version_code: number
    version_name: string
    download_url: string
    sha256: string
    size_bytes: number
    notes: string | null
    min_supported_version_code: number
    // Gói của APK; có thì chỉ nhận khi trùng gói đang chạy.
    package_name?: string | null
  } | null
}

const NO_UPDATE: ReleaseInfo = { update_available: false, required: false, latest: null }

// Bản thử (gói .debug) không nhận bản chính thức: khác gói, bấm vào là cài thêm app khác chứ không cập nhật.
// Bản thử cập nhật bằng cách cài APK debug mới.
export async function checkRelease(): Promise<ReleaseInfo> {
  if (isDebugBuild()) return NO_UPDATE
  const release = await apiGet<ReleaseInfo>(`/device/release?current_version_code=${getAppVersion().code}`)
  const pkg = release.latest?.package_name
  if (isNative && pkg && pkg !== getAppId()) return NO_UPDATE
  return release
}

export async function startApkDownload(release: ReleaseInfo): Promise<boolean> {
  if (!release.latest) return false
  return openExternal(release.latest.download_url)
}

// Trên trình duyệt không có APK để cập nhật: không hiện dải báo bản mới.
export const canInstallApk = isNative
