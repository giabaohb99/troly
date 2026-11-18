package vn.io.baohuynh.troly.alarm

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.Uri
import org.json.JSONObject
import vn.io.baohuynh.troly.plugin.AlarmPlugin
import vn.io.baohuynh.troly.queue.EventQueue
import vn.io.baohuynh.troly.queue.QueuedEvent
import vn.io.baohuynh.troly.queue.UploadScheduler
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID

/**
 * Báo thức tới giờ: hiện thông báo. Nút trên thông báo: Xong (việc), Đã biết (sự kiện), Hoãn 10 phút; mỗi lần bấm
 * ghi sự kiện `reminder_action` vào hàng đợi gửi /device/events (30 mục 3.8, 3.9).
 */
class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val key = intent.data?.schemeSpecificPart ?: return
        val store = ReminderStore(context)
        when (intent.action) {
            ACTION_FIRE -> {
                if (key in store.handled) return
                val reminder = store.find(key) ?: return
                store.markFired(key)
                ReminderNotifier.show(context, reminder)
            }
            ACTION_DONE, ACTION_ACK, ACTION_SNOOZE -> {
                val reminder = store.find(key)
                val action = when (intent.action) {
                    ACTION_DONE -> "done"
                    ACTION_ACK -> "ack"
                    else -> "snooze"
                }
                val now = System.currentTimeMillis()
                ReminderNotifier.cancel(context, key)
                if (action == "snooze") store.snooze(key, now + ReminderPlan.SNOOZE_MILLIS) else store.markHandled(key)
                ReminderScheduler.apply(context, now)
                if (reminder != null) {
                    val id = UUID.randomUUID().toString()
                    EventQueue.get(context).add(QueuedEvent(id, toActionJson(id, reminder, action, now).toString()), now)
                    UploadScheduler.enqueue(context)
                    AlarmPlugin.emitAction(reminder, action)
                }
            }
        }
    }

    companion object {
        const val ACTION_FIRE = "vn.io.baohuynh.troly.REMINDER_FIRE"
        const val ACTION_DONE = "vn.io.baohuynh.troly.REMINDER_DONE"
        const val ACTION_ACK = "vn.io.baohuynh.troly.REMINDER_ACK"
        const val ACTION_SNOOZE = "vn.io.baohuynh.troly.REMINDER_SNOOZE"

        private val ZONE: ZoneId = ZoneId.of("Asia/Ho_Chi_Minh")

        fun actionIntent(context: Context, action: String, key: String): PendingIntent {
            val intent = Intent(context, ReminderReceiver::class.java)
                .setAction(action)
                .setData(Uri.Builder().scheme("troly-reminder").opaquePart(key).build())
            return PendingIntent.getBroadcast(context, (action + key).hashCode(), intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        }

        private fun iso(millis: Long): String =
            OffsetDateTime.ofInstant(Instant.ofEpochMilli(millis), ZONE).format(DateTimeFormatter.ISO_OFFSET_DATE_TIME)

        /** Một phần tử `events` kiểu reminder_action (11 mục 3.5); app_package để null. */
        fun toActionJson(clientEventId: String, reminder: Reminder, action: String, now: Long): JSONObject =
            JSONObject()
                .put("client_event_id", clientEventId)
                .put("kind", "reminder_action")
                .put("app_package", JSONObject.NULL)
                .put("posted_at", iso(now))
                .put(
                    "payload",
                    JSONObject()
                        .put("reminder_key", reminder.key)
                        .put("source", reminder.source)
                        .put("source_id", reminder.sourceId ?: JSONObject.NULL)
                        .put("action", action)
                        .put("at", iso(now)),
                )
    }
}

/** Khởi động máy, cập nhật app, đổi giờ, đổi múi giờ, đổi quyền báo thức chính xác: đặt lại mọi báo thức. */
class ReminderBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        ReminderScheduler.apply(context)
        ReminderSync.syncNow(context)
    }
}
