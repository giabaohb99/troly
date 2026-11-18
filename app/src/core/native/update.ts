import { apiGet } from '@/core/api/http-client'
import { getAppVersion, isNative } from '@/core/config'
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
  } | null
}

export function checkRelease(): Promise<ReleaseInfo> {
  return apiGet<ReleaseInfo>(`/device/release?current_version_code=${getAppVersion().code}`)
}

export async function startApkDownload(release: ReleaseInfo): Promise<boolean> {
  if (!release.latest) return false
  return openExternal(release.latest.download_url)
}

// Trên trình duyệt không có APK để cập nhật: không hiện dải báo bản mới.
export const canInstallApk = isNative
