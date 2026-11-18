package vn.io.baohuynh.troly.queue

import android.content.Context
import android.os.Build
import org.json.JSONObject
import vn.io.baohuynh.troly.BuildConfig
import vn.io.baohuynh.troly.notify.DeviceState
import vn.io.baohuynh.troly.secure.SecureStore
import vn.io.baohuynh.troly.system.PermissionStatus

/**
 * Nhịp tim và tải cấu hình (hợp đồng ở mục 5 bảng việc): POST /device/heartbeat gửi trạng thái máy,
 * nhận config_revision; khác bản đang có thì GET /device/config (If-None-Match, 304 khi không đổi).
 * Chạy trong việc nền.
 */
object DeviceSync {
    /** Trả false khi thiết bị bị thu hồi. */
    fun run(context: Context): Boolean {
        val api = DeviceApi(context)
        if (!api.hasToken()) return true
        val state = DeviceState(context)
        val permissions = PermissionStatus.read(context)
        val heartbeat = JSONObject()
            .put("app_version_code", BuildConfig.VERSION_CODE)
            .put("app_version_name", BuildConfig.VERSION_NAME)
            .put("manufacturer", Build.MANUFACTURER)
            .put("default_sms_package", permissions.defaultSmsPackage ?: JSONObject.NULL)
            .put("notification_access", permissions.notificationListener)
            .put("listener_connected", state.listenerConnected)
            .put("notifications_enabled", permissions.notifications)
            .put("exact_alarm_allowed", permissions.exactAlarm)
            .put("battery_optimization_ignored", permissions.batteryUnrestricted)
            .put("queue_size", EventQueue.get(context).size())
            .put("otp_blocked_today", state.count(DeviceState.OTP_BLOCKED_TODAY))
        val beat = api.request("POST", "/device/heartbeat", heartbeat)
        if (handleRevoked(context, beat)) return false
        val revision = beat.data?.optString("config_revision")?.takeIf { it.isNotEmpty() }
        if (beat.status == 200 && revision != null && revision == state.configRevision) return true
        return refreshConfig(context, state, api)
    }

    fun refreshConfig(context: Context, state: DeviceState = DeviceState(context), api: DeviceApi = DeviceApi(context)): Boolean {
        val headers = state.configEtag?.let { mapOf("If-None-Match" to it) } ?: emptyMap()
        val result = api.request("GET", "/device/config", headers = headers)
        if (handleRevoked(context, result)) return false
        if (result.status != 200) return true
        val data = result.data ?: return true
        data.optJSONArray("listened_apps")?.let { state.listenedApps = DeviceState.parseApps(it.toString()) }
        data.optJSONArray("sms_brand_senders")?.let { array -> state.brandSenders = List(array.length()) { array.getString(it) } }
        data.optJSONObject("upload")?.optInt("batch_max", 50)?.let { state.batchMax = it }
        state.configRevision = data.optString("revision").takeIf { it.isNotEmpty() }
        state.configEtag = result.header("ETag")
        return true
    }

    /** 401 DEVICE_REVOKED: dừng hẳn, xóa mã thiết bị; giao diện sẽ đưa về đăng nhập. */
    fun handleRevoked(context: Context, result: ApiResult): Boolean {
        if (result.status != 401 || result.code != "DEVICE_REVOKED") return false
        SecureStore.remove(context, SecureStore.DEVICE_TOKEN)
        DeviceState(context).deviceRevoked = true
        return true
    }
}
