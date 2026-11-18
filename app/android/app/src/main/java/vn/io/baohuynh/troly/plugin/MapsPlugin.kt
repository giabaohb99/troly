package vn.io.baohuynh.troly.plugin

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import java.util.Locale

/**
 * Mở Google Maps (30 mục 3.12, 41 mục 7). Dẫn đường: `google.navigation:` chế độ xe hai bánh (`mode=l`), tránh
 * cao tốc (`avoid=h`), gắn gói Maps. Không có Maps thì mở link chỉ đường https bằng trình duyệt.
 */
@CapacitorPlugin(name = "Maps")
class MapsPlugin : Plugin() {

    @PluginMethod
    fun isMapsInstalled(call: PluginCall) {
        call.resolve(JSObject().put("value", isMapsInstalled(context)))
    }

    @PluginMethod
    fun navigate(call: PluginCall) {
        val lat = call.getDouble("lat")
        val lng = call.getDouble("lng")
        val query = call.getString("query")?.trim()?.takeIf { it.isNotEmpty() }
        val mode = call.getString("mode")?.takeIf { it in MODES } ?: "l"
        val avoid = call.getString("avoid")?.takeIf { it.matches(Regex("^[htf]{1,3}$")) }
        val target = when {
            lat != null && lng != null -> String.format(Locale.US, "%.6f,%.6f", lat, lng)
            query != null -> Uri.encode(query)
            else -> return call.reject("Thiếu tọa độ hoặc tên điểm.")
        }
        if (isMapsInstalled(context)) {
            val uri = Uri.parse("google.navigation:q=$target&mode=$mode" + (avoid?.let { "&avoid=$it" } ?: ""))
            val intent = Intent(Intent.ACTION_VIEW, uri).setPackage(MAPS_PACKAGE).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            if (start(intent)) return call.resolve(JSObject().put("opened", "maps"))
        }
        val fallback = call.getString("fallbackUrl")?.takeIf { it.startsWith("https://") }
            ?: "https://www.google.com/maps/dir/?api=1&destination=$target&travelmode=two-wheeler&dir_action=navigate"
        if (openBrowser(fallback)) call.resolve(JSObject().put("opened", "browser")) else call.reject("Không mở được bản đồ.")
    }

    /** Mở link Maps (chỉ đường cả ngày, xem một điểm) do máy chủ dựng; chỉ nhận https. */
    @PluginMethod
    fun openUrl(call: PluginCall) {
        val url = call.getString("url")?.takeIf { it.startsWith("https://") } ?: return call.reject("Link không an toàn.")
        if (isMapsInstalled(context)) {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).setPackage(MAPS_PACKAGE).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            if (start(intent)) return call.resolve(JSObject().put("opened", "maps"))
        }
        if (openBrowser(url)) call.resolve(JSObject().put("opened", "browser")) else call.reject("Không mở được bản đồ.")
    }

    private fun openBrowser(url: String): Boolean =
        start(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addCategory(Intent.CATEGORY_BROWSABLE).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))

    private fun start(intent: Intent): Boolean = try {
        context.startActivity(intent)
        true
    } catch (_: ActivityNotFoundException) {
        false
    }

    companion object {
        const val MAPS_PACKAGE = "com.google.android.apps.maps"
        private val MODES = setOf("d", "b", "l", "w")

        fun isMapsInstalled(context: Context): Boolean = try {
            context.packageManager.getPackageInfo(MAPS_PACKAGE, 0)
            context.packageManager.getApplicationInfo(MAPS_PACKAGE, 0).enabled
        } catch (_: Exception) {
            false
        }
    }
}
