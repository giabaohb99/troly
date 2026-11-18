package vn.io.baohuynh.troly.plugin

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.PermissionState
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import com.getcapacitor.annotation.Permission
import com.getcapacitor.annotation.PermissionCallback
import vn.io.baohuynh.troly.system.PermissionStatus

/**
 * Quyền và trang cài đặt hệ thống cho màn Thiết lập máy (30 mục 3.10). Gọi qua src/core/native/system.ts.
 * Danh sách "Ứng dụng không bao giờ ngủ" của Samsung không đọc được từ app: chỉ mở được trang.
 */
@CapacitorPlugin(
    name = "System",
    permissions = [Permission(alias = "notifications", strings = [Manifest.permission.POST_NOTIFICATIONS])],
)
class SystemPlugin : Plugin() {

    private fun snapshot(): JSObject {
        val s = PermissionStatus.read(context)
        return JSObject()
            .put("notifications", s.notifications)
            .put("notificationListener", s.notificationListener)
            .put("batteryUnrestricted", s.batteryUnrestricted)
            .put("exactAlarm", s.exactAlarm)
            .put("installPackages", s.installPackages)
            .put("defaultSmsPackage", s.defaultSmsPackage)
            .put("defaultSmsLabel", s.defaultSmsPackage?.let(::labelOf))
            .put("manufacturer", Build.MANUFACTURER)
            .put("model", Build.MODEL)
            .put("androidSdk", Build.VERSION.SDK_INT)
    }

    private fun labelOf(packageName: String): String? = try {
        val pm = context.packageManager
        pm.getApplicationLabel(pm.getApplicationInfo(packageName, 0)).toString()
    } catch (error: PackageManager.NameNotFoundException) {
        null
    }

    @PluginMethod
    fun getPermissions(call: PluginCall) = call.resolve(snapshot())

    /** App đã cài trên máy hay chưa (gói phải khai trong <queries> của manifest). */
    @PluginMethod
    fun getInstalledApps(call: PluginCall) {
        val packages = call.getArray("packages")?.toList<String>().orEmpty()
        val installed = JSArray()
        packages.filter { labelOf(it) != null }.forEach { installed.put(it) }
        call.resolve(JSObject().put("installed", installed))
    }

    @PluginMethod
    fun requestNotifications(call: PluginCall) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU || getPermissionState("notifications") == PermissionState.GRANTED) {
            call.resolve(snapshot())
            return
        }
        requestPermissionForAlias("notifications", call, "notificationsCallback")
    }

    @PermissionCallback
    private fun notificationsCallback(call: PluginCall) = call.resolve(snapshot())

    @PluginMethod
    fun openSettings(call: PluginCall) {
        val packageUri = Uri.parse("package:${context.packageName}")
        val intent = when (call.getString("target")) {
            "notification_listener" -> Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
            "app_details" -> Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, packageUri)
            "battery" -> Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, packageUri)
            // Intent Samsung công bố cho danh sách "Ứng dụng không bao giờ ngủ" (activity_type = 2).
            "samsung_never_sleeping" -> Intent("com.samsung.android.sm.ACTION_OPEN_CHECKABLE_LISTACTIVITY")
                .setPackage("com.samsung.android.lool")
                .putExtra("activity_type", 2)
            "exact_alarm" -> if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM, packageUri)
            } else {
                null
            }
            "unknown_sources" -> Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, packageUri)
            "notifications" -> Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
            "default_apps" -> Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS)
            else -> null
        }
        if (intent == null) {
            call.resolve(JSObject().put("opened", false))
            return
        }
        val opened = try {
            activity.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            true
        } catch (error: ActivityNotFoundException) {
            false
        } catch (error: SecurityException) {
            false
        }
        call.resolve(JSObject().put("opened", opened))
    }

    // Người dùng quay lại từ trang cài đặt: báo giao diện kiểm lại.
    override fun handleOnResume() {
        super.handleOnResume()
        notifyListeners("permissionsChanged", snapshot())
    }
}
