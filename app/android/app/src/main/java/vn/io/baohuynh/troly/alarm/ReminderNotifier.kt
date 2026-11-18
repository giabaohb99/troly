package vn.io.baohuynh.troly.alarm

import android.app.Notification
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
    const val CHANNEL_TRANSACTION = "giao-dich"
    const val CHANNEL_IMPORTANT = "tin-quan-trong"
    const val CHANNEL_CHAT = "tro-ly-tra-loi"

    fun ensureChannels(context: Context) {
        val manager = context.getSystemService(NotificationManager::class.java)
        val alarmSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
        val alarm = NotificationChannel(CHANNEL_ALARM, "Báo thức", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Chỉ khi bảo trợ lý đặt báo thức: kêu liên tục tới khi tắt"
            setSound(alarmSound, AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build())
            enableVibration(true)
        }
        manager.createNotificationChannels(
            listOf(
                NotificationChannel(CHANNEL_REMINDER, "Nhắc lịch", NotificationManager.IMPORTANCE_HIGH).apply { description = "Nhắc sự kiện và việc: kêu một tiếng như tin nhắn" },
                alarm,
                NotificationChannel(CHANNEL_UPDATE, "Cập nhật app", NotificationManager.IMPORTANCE_DEFAULT),
                NotificationChannel(CHANNEL_SYSTEM, "Hệ thống", NotificationManager.IMPORTANCE_LOW),
                NotificationChannel(CHANNEL_TRANSACTION, "Giao dịch mới", NotificationManager.IMPORTANCE_DEFAULT).apply {
                    description = "Báo khi trợ lý ghi một khoản chi, thu từ ngân hàng"
                },
                NotificationChannel(CHANNEL_IMPORTANT, "Tin quan trọng", NotificationManager.IMPORTANCE_HIGH).apply {
                    description = "Tin của người quan trọng hoặc có từ khóa gấp"
                },
                NotificationChannel(CHANNEL_CHAT, "Trợ lý trả lời", NotificationManager.IMPORTANCE_HIGH).apply {
                    description = "Trợ lý trả lời xong khi app không ở màn hình"
                },
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
        // QĐ-39: nhắc thường là thông báo kêu một tiếng. Kiểu báo thức (chỉ khi có cờ alarm) hiện toàn màn hình nếu
        // máy cho phép và kêu liên tục tới khi bấm.
        if (reminder.isAlarm) {
            builder.setOngoing(true).setFullScreenIntent(openIntent(context, reminder), true)
        } else if (NotifyPrefs(context).shouldSilence()) {
            // Tắt kêu và rung, hoặc đang trong giờ yên lặng: vẫn hiện, không kêu (QĐ-38).
            builder.setSilent(true)
        }
        val notification = builder.build()
        if (reminder.isAlarm) notification.flags = notification.flags or Notification.FLAG_INSISTENT
        try {
            manager.notify(notificationId(reminder.key), notification)
        } catch (_: SecurityException) {
            // Mất quyền POST_NOTIFICATIONS giữa chừng: bỏ qua, màn Lịch đã báo thiếu quyền.
        }
    }

    /** Thông báo do máy chủ gửi qua /device/notices (giao dịch mới, tin quan trọng). */
    fun showNotice(context: Context, id: String, channel: String, title: String, body: String?, deepLink: String?) {
        ensureChannels(context)
        val manager = NotificationManagerCompat.from(context)
        if (!manager.areNotificationsEnabled()) return
        val link = ReminderPlan.safeDeepLink(deepLink) ?: "troly://"
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(link), context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val builder = NotificationCompat.Builder(context, channel)
            .setSmallIcon(R.drawable.ic_stat_reminder)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(body?.let { NotificationCompat.BigTextStyle().bigText(it) })
            .setAutoCancel(true)
            .setContentIntent(PendingIntent.getActivity(context, id.hashCode(), intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
        if (NotifyPrefs(context).shouldSilence()) builder.setSilent(true)
        try {
            manager.notify(("notice:$id").hashCode(), builder.build())
        } catch (_: SecurityException) {
            // Mất quyền thông báo: bỏ qua.
        }
    }

    /**
     * Trợ lý trả lời xong khi app không ở màn hình (QĐ-41). Không báo hai lần cho cùng [messageId]. Bấm mở đúng tin;
     * tin có tệp thì có nút Mở tệp.
     */
    fun showChatDone(context: Context, messageId: String, deepLink: String, body: String?, fileLink: String?, title: String? = null) {
        val prefs = NotifyPrefs(context)
        if (!prefs.chatDone || !prefs.markChatNotified(messageId)) return
        ensureChannels(context)
        val manager = NotificationManagerCompat.from(context)
        if (!manager.areNotificationsEnabled()) return
        val builder = NotificationCompat.Builder(context, CHANNEL_CHAT)
            .setSmallIcon(R.drawable.ic_stat_reminder)
            .setContentTitle(title ?: if (fileLink != null) "Trợ lý đã xong tệp" else "Trợ lý đã trả lời")
            .setContentText(body)
            .setStyle(body?.let { NotificationCompat.BigTextStyle().bigText(it) })
            .setAutoCancel(true)
            .setContentIntent(linkIntent(context, deepLink, "chat:$messageId"))
        fileLink?.let { builder.addAction(0, "Mở tệp", linkIntent(context, it, "chat-file:$messageId")) }
        if (prefs.shouldSilence()) builder.setSilent(true)
        try {
            manager.notify(("chat:$messageId").hashCode(), builder.build())
        } catch (_: SecurityException) {
            // Mất quyền thông báo: bỏ qua.
        }
    }

    private fun linkIntent(context: Context, link: String, key: String): PendingIntent {
        val safe = ReminderPlan.safeDeepLink(link) ?: "troly://"
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(safe), context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        return PendingIntent.getActivity(context, key.hashCode(), intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    fun cancel(context: Context, key: String) = NotificationManagerCompat.from(context).cancel(notificationId(key))
}
