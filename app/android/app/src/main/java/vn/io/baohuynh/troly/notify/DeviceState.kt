package vn.io.baohuynh.troly.notify

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.ZoneId

/**
 * Trạng thái của plugin nghe thông báo trên máy: danh sách app được nghe và cấu hình lấy từ
 * GET /device/config (máy chủ là gốc), bộ đếm theo ngày, lần nhận sự kiện cuối.
 */
class DeviceState(context: Context) {
    private val prefs: SharedPreferences = context.applicationContext.getSharedPreferences("troly_device", Context.MODE_PRIVATE)

    var listenedApps: List<ListenedApp>
        get() = prefs.getString(KEY_APPS, null)?.let(::parseApps) ?: DEFAULT_APPS
        set(value) = prefs.edit().putString(KEY_APPS, JSONArray(value.map {
            JSONObject().put("package_name", it.packageName).put("purpose", it.purpose).put("enabled", it.enabled)
        }).toString()).apply()

    var configRevision: String?
        get() = prefs.getString("config_revision", null)
        set(value) = prefs.edit().putString("config_revision", value).apply()

    var configEtag: String?
        get() = prefs.getString("config_etag", null)
        set(value) = prefs.edit().putString("config_etag", value).apply()

    var brandSenders: List<String>
        get() = prefs.getString("brand_senders", null)?.let { json ->
            val array = JSONArray(json)
            List(array.length()) { array.getString(it) }
        } ?: OtpDetector.DEFAULT_SMS_BRAND_SENDERS
        set(value) = prefs.edit().putString("brand_senders", JSONArray(value).toString()).apply()

    var batchMax: Int
        get() = prefs.getInt("batch_max", 50)
        set(value) = prefs.edit().putInt("batch_max", value.coerceIn(1, 50)).apply()

    var listenerConnected: Boolean
        get() = prefs.getBoolean("listener_connected", false)
        set(value) = prefs.edit().putBoolean("listener_connected", value).apply()

    var lastEventAt: Long
        get() = prefs.getLong("last_event_at", 0)
        set(value) = prefs.edit().putLong("last_event_at", value).apply()

    var deviceRevoked: Boolean
        get() = prefs.getBoolean("device_revoked", false)
        set(value) = prefs.edit().putBoolean("device_revoked", value).apply()

    var otpRejectedByServer: Int
        get() = prefs.getInt("otp_rejected_server", 0)
        set(value) = prefs.edit().putInt("otp_rejected_server", value).apply()

    // Bộ đếm theo ngày giờ Việt Nam: sang ngày mới thì về 0. Chỉ đếm, không lưu nội dung.
    @Synchronized
    fun increment(counter: String) {
        resetIfNewDay()
        prefs.edit().putInt(counter, prefs.getInt(counter, 0) + 1).apply()
    }

    @Synchronized
    fun count(counter: String): Int {
        resetIfNewDay()
        return prefs.getInt(counter, 0)
    }

    private fun resetIfNewDay() {
        val today = LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh")).toString()
        if (prefs.getString("counter_day", null) != today) {
            prefs.edit().putString("counter_day", today).putInt(DROPPED_TODAY, 0).putInt(OTP_BLOCKED_TODAY, 0).apply()
        }
    }

    companion object {
        const val DROPPED_TODAY = "dropped_today"
        const val OTP_BLOCKED_TODAY = "otp_blocked_today"
        private const val KEY_APPS = "listened_apps"

        // 7 dòng mặc định (30 mục 3.6), dùng tới khi tải được cấu hình từ máy chủ.
        val DEFAULT_APPS = listOf(
            ListenedApp("com.VCB", "expense", true),
            ListenedApp("vn.com.techcombank.bb.app", "expense", true),
            ListenedApp("com.mservice.momotransfer", "expense", true),
            ListenedApp("com.zing.zalo", "inbox", true),
            ListenedApp("org.telegram.messenger", "inbox", true),
            ListenedApp("com.facebook.orca", "inbox", true),
            ListenedApp(FilterRules.SMS_DEFAULT, "inbox", true),
        )

        fun parseApps(json: String): List<ListenedApp> {
            val array = JSONArray(json)
            return List(array.length()) {
                val item = array.getJSONObject(it)
                ListenedApp(item.getString("package_name"), item.optString("purpose", "inbox"), item.optBoolean("enabled", true))
            }
        }
    }
}
