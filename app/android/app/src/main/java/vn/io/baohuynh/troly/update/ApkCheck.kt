package vn.io.baohuynh.troly.update

import java.io.InputStream
import java.io.OutputStream
import java.security.MessageDigest

/**
 * Luật tải và kiểm APK cập nhật (30 mục 3.11), tách khỏi Android để có JUnit: chép kèm băm sha256 và báo tiến
 * trình, so mã băm, so tên gói, đặt tên tệp.
 */
object ApkCheck {
    const val DIR = "updates"

    /** Tên tệp trong filesDir/updates; một bản một tệp, bản cũ xóa khi tải bản mới. */
    fun fileName(versionCode: Int): String = "troly-$versionCode.apk"

    /** Mã băm máy chủ gửi có thể viết hoa, có khoảng trắng; rỗng thì không nhận. */
    fun sha256Matches(expected: String?, actual: String): Boolean {
        val e = expected?.trim()?.lowercase().orEmpty()
        return e.length == 64 && e == actual.lowercase()
    }

    /** Phần trăm 0 tới 100; chưa biết cỡ tệp thì -1. */
    fun percent(done: Long, total: Long): Int = if (total <= 0) -1 else ((done * 100) / total).coerceIn(0, 100).toInt()

    /** Kết quả kiểm tệp đã tải: null là đạt, không thì mã lỗi gửi giao diện. */
    fun verdict(expectedSha: String?, actualSha: String, archivePackage: String?, runningPackage: String): String? = when {
        !sha256Matches(expectedSha, actualSha) -> "sha"
        archivePackage != runningPackage -> "package"
        else -> null
    }

    /**
     * Chép luồng sang tệp, băm sha256 trong lúc chép. onProgress chỉ gọi khi phần trăm đổi (hoặc mỗi 1 MB khi chưa
     * biết cỡ). Quá maxBytes thì dừng. Trả mã băm hex chữ thường.
     */
    fun copyWithHash(input: InputStream, output: OutputStream, total: Long, maxBytes: Long, onProgress: (done: Long, percent: Int) -> Unit): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(64 * 1024)
        var done = 0L
        var lastPercent = -2
        var lastMb = -1L
        while (true) {
            val n = input.read(buffer)
            if (n < 0) break
            done += n
            if (done > maxBytes) throw TooLargeException()
            digest.update(buffer, 0, n)
            output.write(buffer, 0, n)
            val p = percent(done, total)
            if (p >= 0 && p != lastPercent) {
                lastPercent = p
                onProgress(done, p)
            } else if (p < 0 && done / MB != lastMb) {
                lastMb = done / MB
                onProgress(done, p)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    class TooLargeException : java.io.IOException("Tệp quá lớn")

    private const val MB = 1024L * 1024
}
