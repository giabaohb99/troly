package vn.io.baohuynh.troly.system

import android.app.AlarmManager
import android.app.NotificationManager
import android.content.ComponentName
import android.content.Context
import android.os.Build
import android.os.PowerManager
import android.provider.Telephony
import vn.io.baohuynh.troly.notify.TrolyNotificationListener

/** Trạng thái các quyền và cài đặt hệ thống (30 mục 3.10), đọc lại mỗi khi app quay lại tiền cảnh. */
data class PermissionSnapshot(
    val notifications: Boolean,
    val notificationListener: Boolean,
    val batteryUnrestricted: Boolean,
    val exactAlarm: Boolean,
    val installPackages: Boolean,
    val defaultSmsPackage: String?,
)

object PermissionStatus {
    fun read(context: Context): PermissionSnapshot {
        val notificationManager = context.getSystemService(NotificationManager::class.java)
        val power = context.getSystemService(PowerManager::class.java)
        val alarms = context.getSystemService(AlarmManager::class.java)
        val listener = ComponentName(context, TrolyNotificationListener::class.java)
        return PermissionSnapshot(
            notifications = notificationManager.areNotificationsEnabled(),
            notificationListener = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
                notificationManager.isNotificationListenerAccessGranted(listener)
            } else {
                android.provider.Settings.Secure.getString(context.contentResolver, "enabled_notification_listeners")
                    ?.contains(listener.flattenToString()) == true
            },
            batteryUnrestricted = power.isIgnoringBatteryOptimizations(context.packageName),
            exactAlarm = Build.VERSION.SDK_INT < Build.VERSION_CODES.S || alarms.canScheduleExactAlarms(),
            installPackages = context.packageManager.canRequestPackageInstalls(),
            defaultSmsPackage = Telephony.Sms.getDefaultSmsPackage(context),
        )
    }
}
