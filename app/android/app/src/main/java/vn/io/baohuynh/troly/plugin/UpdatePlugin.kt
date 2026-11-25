package vn.io.baohuynh.troly.plugin

import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.activity.result.ActivityResult
import androidx.core.content.FileProvider
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.ActivityCallback
import com.getcapacitor.annotation.CapacitorPlugin
import vn.io.baohuynh.troly.update.ApkCheck
import java.io.File
import java.io.FileInputStream
import java.io.IOException
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Cập nhật APK trong app (30 mục 3.11, sửa lỗi 1.0.9): tải vào filesDir/updates (không qua trình duyệt), báo tiến
 * trình qua sự kiện `progress`, kiểm sha256 và tên gói, sai thì xóa. Cài bằng trình cài đặt của Android qua
 * FileProvider; chưa được phép cài từ nguồn này thì mở đúng trang cài đặt đó và báo lại khi người dùng quay về.
 * Gọi qua src/core/native/update.ts. Mã lỗi: args, busy, http, network, size, storage, sha, package, not_allowed,
 * settings.
 */
@CapacitorPlugin(name = "Update")
class UpdatePlugin : Plugin() {
    private val io = Executors.newSingleThreadExecutor()
    private val busy = AtomicBoolean(false)

    private val dir: File get() = File(context.filesDir, ApkCheck.DIR)

    @PluginMethod
    fun download(call: PluginCall) {
        val url = call.getString("url")
        if (url.isNullOrBlank() || !url.startsWith("https://")) return call.reject("Thiếu link tải.", "args")
        val sha = call.getString("sha256")
        val versionCode = call.getInt("versionCode") ?: 0
        val sizeHint = call.data.optLong("size", 0L)
        if (!busy.compareAndSet(false, true)) return call.reject("Đang tải bản mới.", "busy")
        io.execute {
            try {
                val target = File(dir.apply { mkdirs() }, ApkCheck.fileName(versionCode))
                // Một bản một tệp: bỏ tệp của bản khác và tệp tải dở.
                dir.listFiles()?.filter { it.name != target.name }?.forEach { it.delete() }
                // Đã tải đúng từ lần trước (ví dụ hủy hộp cài) thì dùng lại, không tải lại.
                if (target.exists() && checkFile(target, sha) == null) {
                    call.resolve(JSObject().put("path", target.absolutePath).put("reused", true))
                    return@execute
                }
                target.delete()
                fetch(url, target, sizeHint)
                val problem = checkFile(target, sha)
                if (problem != null) {
                    target.delete()
                    call.reject(if (problem == "sha") "Tệp tải về không khớp mã kiểm." else "Tệp không phải bản của Trợ lý.", problem)
                    return@execute
                }
                call.resolve(JSObject().put("path", target.absolutePath).put("reused", false))
            } catch (error: HttpError) {
                call.reject("Máy chủ trả mã ${error.status}.", "http", JSObject().put("status", error.status))
            } catch (error: ApkCheck.TooLargeException) {
                call.reject("Tệp quá lớn.", "size")
            } catch (error: NoSpaceException) {
                call.reject("Máy không đủ chỗ trống.", "storage")
            } catch (error: IOException) {
                call.reject("Mất mạng khi tải.", "network")
            } finally {
                busy.set(false)
            }
        }
    }

    private fun fetch(url: String, target: File, sizeHint: Long) {
        val part = File(target.parentFile, target.name + ".part")
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 15_000
            readTimeout = 30_000
        }
        try {
            if (connection.responseCode !in 200..299) throw HttpError(connection.responseCode)
            val total = connection.contentLengthLong.takeIf { it > 0 } ?: sizeHint
            if (total > 0 && dir.usableSpace < total + SPARE_BYTES) throw NoSpaceException()
            connection.inputStream.use { input ->
                part.outputStream().use { output ->
                    ApkCheck.copyWithHash(input, output, total, MAX_BYTES) { done, percent ->
                        notifyListeners("progress", JSObject().put("done", done).put("total", total).put("percent", percent))
                    }
                }
            }
            if (!part.renameTo(target)) throw IOException("Không đổi tên được tệp tải")
        } catch (error: IOException) {
            part.delete()
            throw error
        } finally {
            connection.disconnect()
        }
    }

    /** Băm lại tệp và đọc tên gói trong APK; null là đạt. */
    private fun checkFile(file: File, sha: String?): String? {
        val actual = FileInputStream(file).use { ApkCheck.copyWithHash(it, NullOutput, file.length(), Long.MAX_VALUE) { _, _ -> } }
        return ApkCheck.verdict(sha, actual, archivePackage(file), context.packageName)
    }

    @Suppress("DEPRECATION")
    private fun archivePackage(file: File): String? {
        val pm = context.packageManager
        val info = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            pm.getPackageArchiveInfo(file.absolutePath, PackageManager.PackageInfoFlags.of(0))
        } else {
            pm.getPackageArchiveInfo(file.absolutePath, 0)
        }
        return info?.packageName
    }

    @PluginMethod
    fun canInstall(call: PluginCall) = call.resolve(JSObject().put("allowed", allowed()))

    private fun allowed(): Boolean = context.packageManager.canRequestPackageInstalls()

    /** Mở trang *Cài ứng dụng không rõ nguồn gốc* của riêng Trợ lý; quay về thì trả quyền hiện tại. */
    @PluginMethod
    fun openInstallSettings(call: PluginCall) {
        val intent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}"))
        try {
            startActivityForResult(call, intent, "installSettingsResult")
        } catch (error: ActivityNotFoundException) {
            call.reject("Không mở được trang cài đặt.", "settings")
        }
    }

    @ActivityCallback
    private fun installSettingsResult(call: PluginCall?, result: ActivityResult) {
        call?.resolve(JSObject().put("allowed", allowed()))
    }

    /** Mở trình cài đặt của Android cho tệp đã tải và kiểm. */
    @PluginMethod
    fun install(call: PluginCall) {
        val file = call.getString("path")?.let(::File)?.canonicalFile
        val root = dir.canonicalFile
        if (file == null || file.parentFile != root || !file.exists()) return call.reject("Không thấy tệp đã tải.", "args")
        if (!allowed()) return call.reject("Chưa cho phép cài từ Trợ lý.", "not_allowed")
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            context.startActivity(intent)
            call.resolve()
        } catch (error: ActivityNotFoundException) {
            call.reject("Không mở được trình cài đặt.", "settings")
        }
    }

    /** Dự phòng: mở trang tải bằng trình duyệt hệ thống (không dùng Custom Tab, tải tệp trên Samsung không chắc). */
    @PluginMethod
    fun openBrowser(call: PluginCall) {
        val url = call.getString("url")
        if (url.isNullOrBlank() || !url.startsWith("https://")) return call.reject("Link không hợp lệ.", "args")
        try {
            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addCategory(Intent.CATEGORY_BROWSABLE).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            call.resolve()
        } catch (error: ActivityNotFoundException) {
            call.reject("Không có trình duyệt.", "settings")
        }
    }

    /** Xóa tệp cập nhật còn lại (gọi khi không có bản mới, tức đã cài xong). */
    @PluginMethod
    fun cleanup(call: PluginCall) {
        if (!busy.get()) dir.listFiles()?.forEach { it.delete() }
        call.resolve()
    }

    private class HttpError(val status: Int) : IOException("HTTP $status")

    private class NoSpaceException : IOException("Hết chỗ trống")

    private object NullOutput : OutputStream() {
        override fun write(b: Int) = Unit

        override fun write(b: ByteArray, off: Int, len: Int) = Unit
    }

    companion object {
        private const val MAX_BYTES = 300L * 1024 * 1024
        private const val SPARE_BYTES = 20L * 1024 * 1024
    }
}
