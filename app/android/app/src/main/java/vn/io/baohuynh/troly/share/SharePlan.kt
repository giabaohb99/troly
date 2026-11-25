package vn.io.baohuynh.troly.share

/**
 * Luật thuần cho chia sẻ từ app khác vào Trợ lý (QĐ-51 bước 2), tách khỏi Android để kiểm bằng JUnit:
 * loại tệp nhận, tên tệp an toàn khi chép vào bộ nhớ đệm, chữ gửi kèm.
 */
object SharePlan {
    const val MAX_FILES = 4
    const val MAX_BYTES = 25L * 1024 * 1024
    private const val DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    private val ACCEPTED = setOf("application/pdf", DOCX, "text/plain", "text/markdown")
    private val ACCEPTED_EXT = setOf("pdf", "docx", "txt", "md", "markdown", "jpg", "jpeg", "png", "webp", "gif", "heic", "heif")

    /** Nhận ảnh và các loại tệp máy chủ đọc được (như ô đính kèm của chat). Mime rỗng hoặc chung chung thì xét đuôi. */
    fun accepts(mime: String?, name: String?): Boolean {
        val m = mime?.lowercase()?.substringBefore(';')?.trim().orEmpty()
        if (m.startsWith("image/") || m in ACCEPTED) return true
        val ext = name?.substringAfterLast('.', "")?.lowercase().orEmpty()
        return (m.isEmpty() || m == "application/octet-stream" || m == "*/*") && ext in ACCEPTED_EXT
    }

    /** Tên tệp không có đường dẫn, ký tự lạ, tối đa 120 ký tự; giữ đuôi. Không có tên thì `tep-chia-se.<đuôi>`. */
    fun safeName(raw: String?, fallbackExt: String): String {
        val base = raw?.substringAfterLast('/')?.substringAfterLast('\\')?.replace(Regex("[\\u0000-\\u001f<>:\"|?*]"), "_")?.trim().orEmpty()
        val name = base.ifEmpty { "tep-chia-se.$fallbackExt" }
        if (name.length <= 120) return name
        val dot = name.lastIndexOf('.')
        val ext = if (dot > 0 && name.length - dot <= 10) name.substring(dot) else ""
        return name.take(120 - ext.length) + ext
    }

    fun extensionFor(mime: String?): String = when (mime?.lowercase()) {
        "image/jpeg" -> "jpg"
        "image/png" -> "png"
        "image/webp" -> "webp"
        "application/pdf" -> "pdf"
        DOCX -> "docx"
        "text/plain" -> "txt"
        else -> "bin"
    }

    /** Chữ gửi kèm: tiêu đề (nếu có và chưa nằm trong chữ) rồi chữ; rỗng thì null. */
    fun sharedText(text: String?, subject: String?): String? {
        val t = text?.trim().orEmpty()
        val s = subject?.trim().orEmpty()
        val joined = when {
            s.isEmpty() -> t
            t.isEmpty() -> s
            t.contains(s) -> t
            else -> "$s\n$t"
        }
        return joined.ifEmpty { null }
    }
}
