package vn.io.baohuynh.troly.alarm

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.net.Uri
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import vn.io.baohuynh.troly.MainActivity
import vn.io.baohuynh.troly.R

/** Kênh thông báo và thông báo nhắc (30 mục 3.9): kênh `nhac-lich`, `bao-thuc`, `cap-nhat`, `he-thong`. */
object ReminderNotifier {
    const val CHANNEL_REMINDER = "nhac-lich"
    const val CHANNEL_ALARM = "bao-thuc"
    const val CHANNEL_UPDATE = "cap-nhat"
    const val CHANNEL_SYSTEM = "he-thong"

    fun ensureChannels(context: Context) {
        val manager = context.getSystemService(NotificationManager::class.java)
        val alarmSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
        val alarm = NotificationChannel(CHANNEL_ALARM, "Báo thức", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Mốc cứng như giờ phà, trả phòng"
            setSound(alarmSound, AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build())
            enableVibration(true)
        }
        manager.createNotificationChannels(
            listOf(
                NotificationChannel(CHANNEL_REMINDER, "Nhắc lịch", NotificationManager.IMPORTANCE_HIGH).apply { description = "Nhắc sự kiện và việc" },
                alarm,
                NotificationChannel(CHANNEL_UPDATE, "Cập nhật app", NotificationManager.IMPORTANCE_DEFAULT),
                NotificationChannel(CHANNEL_SYSTEM, "Hệ thống", NotificationManager.IMPORTANCE_LOW),
            ),
        )
    }

    fun notificationId(key: String): Int = key.hashCode()

    /** Mở app tại đường dẫn sâu của nhắc (troly://lich/su-kien/<id>, troly://lich/viec/<id>). */
    fun openIntent(context: Context, reminder: Reminder?): PendingIntent {
        val link = ReminderPlan.safeDeepLink(reminder?.deepLink) ?: "troly://lich"
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(link), context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        return PendingIntent.getActivity(context, link.hashCode(), intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    fun show(context: Context, reminder: Reminder) {
        ensureChannels(context)
        val manager = NotificationManagerCompat.from(context)
        if (!manager.areNotificationsEnabled()) return
        val primary = if (reminder.isTask) ReminderReceiver.ACTION_DONE to "Xong" else ReminderReceiver.ACTION_ACK to "Đã biết"
        val builder = NotificationCompat.Builder(context, if (reminder.isAlarm) CHANNEL_ALARM else CHANNEL_REMINDER)
            .setSmallIcon(R.drawable.ic_stat_reminder)
            .setContentTitle(reminder.title)
            .setContentText(reminder.body)
            .setStyle(reminder.body?.let { NotificationCompat.BigTextStyle().bigText(it) })
            .setWhen(reminder.fireAt)
            .setShowWhen(true)
            .setCategory(if (reminder.isAlarm) NotificationCompat.CATEGORY_ALARM else NotificationCompat.CATEGORY_REMINDER)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(openIntent(context, reminder))
            .addAction(0, primary.second, ReminderReceiver.actionIntent(context, primary.first, reminder.key))
            .addAction(0, "Hoãn 10 phút", ReminderReceiver.actionIntent(context, ReminderReceiver.ACTION_SNOOZE, reminder.key))
        if (reminder.isAlarm) builder.setOngoing(true)
        try {
            manager.notify(notificationId(reminder.key), builder.build())
        } catch (_: SecurityException) {
            // Mất quyền POST_NOTIFICATIONS giữa chừng: bỏ qua, màn Lịch đã báo thiếu quyền.
        }
    }

    fun cancel(context: Context, key: String) = NotificationManagerCompat.from(context).cancel(notificationId(key))
}
