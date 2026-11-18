package vn.io.baohuynh.troly.queue

import android.content.Context
import org.json.JSONObject
import vn.io.baohuynh.troly.BuildConfig
import vn.io.baohuynh.troly.secure.SecureStore
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/** Kết quả một lần gọi api nhóm /device/... [status] = 0 là lỗi mạng. */
data class ApiResult(val status: Int, val body: JSONObject?, val headers: Map<String, String>) {
    val code: String? get() = body?.optJSONObject("data")?.optString("code")?.takeIf { it.isNotEmpty() }
    val data: JSONObject? get() = body?.optJSONObject("data")

    fun header(name: String): String? = headers.entries.firstOrNull { it.key.equals(name, ignoreCase = true) }?.value
}

/**
 * Gọi api bằng mã thiết bị (`Authorization: Device <mã>`, 12 mục 3.2). Chạy trong việc nền, không trên luồng chính.
 * Mã thiết bị không bao giờ trả về JavaScript.
 */
class DeviceApi(private val context: Context) {
    private val base = "${BuildConfig.API_ORIGIN}/api/v1"

    fun hasToken(): Boolean = SecureStore.get(context, SecureStore.DEVICE_TOKEN) != null

    fun request(method: String, path: String, body: JSONObject? = null, headers: Map<String, String> = emptyMap()): ApiResult {
        val token = SecureStore.get(context, SecureStore.DEVICE_TOKEN) ?: return ApiResult(401, null, emptyMap())
        val connection = (URL(base + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 15_000
            readTimeout = 30_000
            setRequestProperty("Authorization", "Device $token")
            setRequestProperty("Accept", "application/json")
            setRequestProperty("X-App-Version", BuildConfig.VERSION_CODE.toString())
            headers.forEach { (key, value) -> setRequestProperty(key, value) }
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }
        }
        return try {
            if (body != null) connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val status = connection.responseCode
            val stream = if (status >= 400) connection.errorStream else connection.inputStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            val parsed = text.takeIf { it.isNotBlank() }?.let { runCatching { JSONObject(it) }.getOrNull() }
            val responseHeaders = connection.headerFields.filterKeys { it != null }.mapValues { it.value.firstOrNull().orEmpty() }
            ApiResult(status, parsed, responseHeaders)
        } catch (error: IOException) {
            ApiResult(0, null, emptyMap())
        } finally {
            connection.disconnect()
        }
    }
}
