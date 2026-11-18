package vn.io.baohuynh.troly.plugin

import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import org.json.JSONObject
import vn.io.baohuynh.troly.queue.UploadScheduler
import vn.io.baohuynh.troly.secure.SecureStore

/** Giao diện gọi qua src/core/native/secure.ts: get, set, remove, clear. */
@CapacitorPlugin(name = "Secure")
class SecurePlugin : Plugin() {

    private fun readKey(call: PluginCall): String? {
        val key = call.getString("key")
        if (key == null || key !in SecureStore.ALLOWED_KEYS) {
            call.reject("Khóa không hợp lệ.")
            return null
        }
        return key
    }

    @PluginMethod
    fun get(call: PluginCall) {
        val key = readKey(call) ?: return
        val value = SecureStore.get(context, key)
        call.resolve(JSObject().put("value", value ?: JSONObject.NULL))
    }

    @PluginMethod
    fun set(call: PluginCall) {
        val key = readKey(call) ?: return
        val value = call.getString("value") ?: return call.reject("Thiếu giá trị cần cất.")
        try {
            SecureStore.set(context, key, value)
            // Vừa có mã thiết bị (đăng ký lần đầu): gửi các sự kiện đang chờ.
            if (key == SecureStore.DEVICE_TOKEN) UploadScheduler.enqueue(context)
            call.resolve()
        } catch (error: Exception) {
            call.reject("Không cất được mã vào kho khóa.", error)
        }
    }

    @PluginMethod
    fun remove(call: PluginCall) {
        val key = readKey(call) ?: return
        SecureStore.remove(context, key)
        call.resolve()
    }

    @PluginMethod
    fun clear(call: PluginCall) {
        SecureStore.clear(context)
        call.resolve()
    }
}
