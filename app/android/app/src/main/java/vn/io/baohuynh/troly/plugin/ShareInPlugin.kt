package vn.io.baohuynh.troly.plugin

import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import androidx.core.content.IntentCompat
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import vn.io.baohuynh.troly.share.SharePlan
import java.io.File
import java.util.UUID

/**
 * Chia sẻ từ app khác vào Trợ lý (QĐ-51 bước 2): nhận ACTION_SEND (chữ, ảnh, tệp) và ACTION_SEND_MULTIPLE, chép
 * tệp vào bộ nhớ đệm của app (quyền đọc URI chỉ tạm thời), rồi báo giao diện bằng sự kiện `shared`
 * `{text, files: [{path, name, mime, size}], skipped}`. Sự kiện được giữ tới khi giao diện nghe (mở app từ chia sẻ).
 */
@CapacitorPlugin(name = "ShareIn")
class ShareInPlugin : Plugin() {

    override fun load() {
        activity?.intent?.let { handle(it) }
    }

    override fun handleOnNewIntent(intent: Intent) {
        super.handleOnNewIntent(intent)
        handle(intent)
    }

    private fun handle(intent: Intent) {
        if (intent.action != Intent.ACTION_SEND && intent.action != Intent.ACTION_SEND_MULTIPLE) return
        // Activity dựng lại (xoay màn, đổi giao diện) vẫn giữ intent cũ: không xử lý hai lần.
        if (intent.getBooleanExtra(HANDLED, false)) return
        intent.putExtra(HANDLED, true)
        val copy = Intent(intent)
        Thread { notifyListeners("shared", read(copy), true) }.start()
    }

    private fun streams(intent: Intent): List<Uri> =
        if (intent.action == Intent.ACTION_SEND_MULTIPLE) {
            IntentCompat.getParcelableArrayListExtra(intent, Intent.EXTRA_STREAM, Uri::class.java).orEmpty()
        } else {
            listOfNotNull(IntentCompat.getParcelableExtra(intent, Intent.EXTRA_STREAM, Uri::class.java))
        }

    private fun read(intent: Intent): JSObject {
        val files = JSArray()
        var skipped = 0
        val all = streams(intent)
        val dir = File(context.cacheDir, "shared/${UUID.randomUUID()}").apply { mkdirs() }
        for (uri in all.take(SharePlan.MAX_FILES)) {
            try {
                var name: String? = null
                var size = -1L
                context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { c ->
                    if (c.moveToFirst()) {
                        name = c.getString(0)
                        if (!c.isNull(1)) size = c.getLong(1)
                    }
                }
                val mime = context.contentResolver.getType(uri) ?: intent.type
                if (!SharePlan.accepts(mime, name) || size > SharePlan.MAX_BYTES) {
                    skipped++
                    continue
                }
                val target = File(dir, SharePlan.safeName(name ?: uri.lastPathSegment, SharePlan.extensionFor(mime)))
                val copied = context.contentResolver.openInputStream(uri)?.use { input ->
                    target.outputStream().use { out -> input.copyTo(out, 64 * 1024) }
                } ?: -1L
                if (copied <= 0 || copied > SharePlan.MAX_BYTES) {
                    target.delete()
                    skipped++
                    continue
                }
                files.put(JSObject().put("path", target.absolutePath).put("name", target.name).put("mime", mime ?: "").put("size", copied))
            } catch (_: Exception) {
                skipped++
            }
        }
        skipped += (all.size - SharePlan.MAX_FILES).coerceAtLeast(0)
        val text = SharePlan.sharedText(intent.getStringExtra(Intent.EXTRA_TEXT), intent.getStringExtra(Intent.EXTRA_SUBJECT))
        return JSObject().put("text", text).put("files", files).put("skipped", skipped)
    }

    /** Xóa tệp đã chép sau khi tải lên xong (hoặc bỏ chia sẻ). */
    @PluginMethod
    fun cleanup(call: PluginCall) {
        File(context.cacheDir, "shared").deleteRecursively()
        call.resolve()
    }

    companion object {
        private const val HANDLED = "vn.io.baohuynh.troly.SHARE_HANDLED"
    }
}
