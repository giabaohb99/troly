package vn.io.baohuynh.troly.alarm

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build

/**
 * Đặt báo thức theo [ReminderPlan] (30 mục 3.9). Nhắc thường: setExactAndAllowWhileIdle; loại báo thức:
 * setAlarmClock (hệ thống thoát Doze để kêu); thiếu quyền báo thức chính xác: setWindow 10 phút.
 * Gọi lại mỗi khi danh sách đổi, khi mở app, sau khởi động máy, cập nhật app, đổi giờ, đổi múi giờ.
 */
object ReminderScheduler {
    private const val WINDOW_MILLIS = 10L * 60_000

    @Synchronized
    fun apply(context: Context, now: Long = System.currentTimeMillis()) {
        val store = ReminderStore(context)
        val items = store.items
        val plan = ReminderPlan.compute(items, store.snoozed, store.handled, store.fired, now)
        val alarms = context.getSystemService(AlarmManager::class.java)
        val wanted = plan.schedule.map { it.key }.toSet()
        for (key in store.scheduledKeys - wanted) alarms.cancel(fireIntent(context, key))
        val byKey = items.associateBy { it.key }
        for (alarm in plan.schedule) set(context, alarms, alarm, byKey[alarm.key])
        store.scheduledKeys = wanted
        for (key in plan.fireNow) {
            val reminder = byKey[key] ?: continue
            store.markFired(key)
            ReminderNotifier.show(context, reminder)
        }
    }

    fun canScheduleExact(context: Context): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.S || context.getSystemService(AlarmManager::class.java).canScheduleExactAlarms()

    private fun set(context: Context, alarms: AlarmManager, alarm: ScheduledAlarm, reminder: Reminder?) {
        val pending = fireIntent(context, alarm.key)
        try {
            when {
                !canScheduleExact(context) -> alarms.setWindow(AlarmManager.RTC_WAKEUP, alarm.fireAt, WINDOW_MILLIS, pending)
                alarm.isAlarm -> alarms.setAlarmClock(AlarmManager.AlarmClockInfo(alarm.fireAt, ReminderNotifier.openIntent(context, reminder)), pending)
                else -> alarms.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, alarm.fireAt, pending)
            }
        } catch (_: SecurityException) {
            // Quyền báo thức chính xác vừa bị thu: lùi về cửa sổ 10 phút.
            alarms.setWindow(AlarmManager.RTC_WAKEUP, alarm.fireAt, WINDOW_MILLIS, pending)
        }
    }

    /** PendingIntent theo khóa nhắc; dữ liệu Uri riêng từng khóa để hủy đúng cái. */
    fun fireIntent(context: Context, key: String): PendingIntent {
        val intent = Intent(context, ReminderReceiver::class.java)
            .setAction(ReminderReceiver.ACTION_FIRE)
            .setData(Uri.Builder().scheme("troly-reminder").opaquePart(key).build())
        return PendingIntent.getBroadcast(context, key.hashCode(), intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }
}
