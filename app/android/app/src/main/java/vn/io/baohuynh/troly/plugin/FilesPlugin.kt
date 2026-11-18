package vn.io.baohuynh.troly.plugin

import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.Intent
import android.net.Uri
import androidx.core.content.FileProvider
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/**
 * Mở tệp bot xuất (QĐ-41): tải link tải tạm (https) về bộ nhớ đệm của app rồi mở bằng trình xem của máy qua
 * FileProvider, cấp quyền đọc. Không có app mở được thì trả opened = false để giao diện mời chia sẻ.
 */
@CapacitorPlugin(name = "Files")
class FilesPlugin : Plugin() {
    private val io = Executors.newSingleThreadExecutor()

    @PluginMethod
    fun open(call: PluginCall) {
        val url = call.getString("url")?.takeIf { it.startsWith("https://") } ?: return call.reject("Link tải không an toàn.")
        val name = safeName(call.getString("name"))
        val mime = call.getString("mime") ?: "application/octet-stream"
        io.execute {
            val file = try {
                download(url, name)
            } catch (error: IOException) {
                return@execute call.reject("Không tải được tệp, thử lại sau.")
            }
            val uri = uriFor(file)
            // Tệp lưu đúng tên (FileProvider trả DISPLAY_NAME theo tên tệp); thêm ClipData, EXTRA_TITLE cho trình xem.
            val intent = Intent(Intent.ACTION_VIEW)
                .setDataAndType(uri, mime)
                .putExtra(Intent.EXTRA_TITLE, name)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
            intent.clipData = ClipData.newUri(context.contentResolver, name, uri)
            val opened = try {
                activity.startActivity(intent)
                true
            } catch (_: ActivityNotFoundException) {
                false
            }
            call.resolve(JSObject().put("opened", opened).put("path", file.absolutePath))
        }
    }

    /** Chia sẻ tệp đã tải (khi máy không có app mở được loại tệp đó). */
    @PluginMethod
    fun share(call: PluginCall) {
        val path = call.getString("path") ?: return call.reject("Thiếu tệp.")
        val file = File(path)
        val exportsDir = File(context.cacheDir, EXPORT_DIR).canonicalFile
        if (!file.canonicalFile.startsWith(exportsDir) || !file.exists()) return call.reject("Tệp không còn, mở lại để tải.")
        val uri = uriFor(file)
        val send = Intent(Intent.ACTION_SEND)
            .setType(call.getString("mime") ?: "application/octet-stream")
            .putExtra(Intent.EXTRA_STREAM, uri)
            .putExtra(Intent.EXTRA_TITLE, file.name)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        send.clipData = ClipData.newUri(context.contentResolver, file.name, uri)
        activity.startActivity(Intent.createChooser(send, "Chia sẻ tệp").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        call.resolve()
    }

    private fun uriFor(file: File): Uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)

    private fun download(url: String, name: String): File {
        val dir = File(context.cacheDir, EXPORT_DIR).apply { mkdirs() }
        // Giữ tối đa 20 tệp gần nhất trong bộ nhớ đệm.
        dir.listFiles()?.sortedByDescending { it.lastModified() }?.drop(20)?.forEach { it.delete() }
        val target = File(dir, name)
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 15_000
            readTimeout = 60_000
        }
        try {
            if (connection.responseCode !in 200..299) throw IOException("HTTP ${connection.responseCode}")
            val length = connection.contentLengthLong
            if (length > MAX_BYTES) throw IOException("Tệp quá lớn")
            connection.inputStream.use { input ->
                target.outputStream().use { output ->
                    val copied = input.copyTo(output)
                    if (copied > MAX_BYTES) throw IOException("Tệp quá lớn")
                }
            }
        } catch (error: IOException) {
            target.delete()
            throw error
        } finally {
            connection.disconnect()
        }
        return target
    }

    companion object {
        private const val EXPORT_DIR = "exports"
        private const val MAX_BYTES = 50L * 1024 * 1024

        /** Bỏ ký tự đường dẫn và ký tự lạ trong tên tệp do máy chủ gửi. */
        fun safeName(raw: String?): String {
            val cleaned = raw.orEmpty().replace(Regex("""[\\/:*?"<>|\u0000-\u001f]"""), "_").trim().trimStart('.')
            return cleaned.take(120).ifEmpty { "tep" }
        }
    }
}
