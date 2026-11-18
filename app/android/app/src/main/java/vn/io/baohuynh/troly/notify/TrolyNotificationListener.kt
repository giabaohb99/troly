package vn.io.baohuynh.troly.notify

import android.content.ComponentName
import android.provider.Telephony
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import org.json.JSONArray
import org.json.JSONObject
import vn.io.baohuynh.troly.queue.EventQueue
import vn.io.baohuynh.troly.queue.QueuedEvent
import vn.io.baohuynh.troly.queue.UploadScheduler
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID
import java.util.concurrent.Executors

/**
 * Dịch vụ nghe thông báo (30 mục 3.6). Hàm gọi lại chạy trên luồng chính nên việc lọc và ghi hàng đợi
 * chạy trên một luồng nền riêng. Không gọi mạng ở đây (Android 15 chặn mạng ngoài vòng đời): chỉ ghi
 * hàng đợi và xếp việc WorkManager.
 */
class TrolyNotificationListener : NotificationListenerService() {

    override fun onListenerConnected() {
        DeviceState(this).listenerConnected = true
    }

    override fun onListenerDisconnected() {
        DeviceState(this).listenerConnected = false
        requestRebind(ComponentName(this, TrolyNotificationListener::class.java))
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val context = applicationContext
        worker.execute { runCatching { handle(context, sbn) } }
    }

    private fun handle(context: android.content.Context, sbn: StatusBarNotification) {
        val state = DeviceState(context)
        val rules = FilterRules(
            ownPackage = context.packageName,
            apps = state.listenedApps,
            defaultSmsPackage = Telephony.Sms.getDefaultSmsPackage(context),
            brandSenders = state.brandSenders,
        )
        // Bước 1 trước khi đọc bất cứ trường nào: app không được nghe thì bỏ ngay, chỉ đếm.
        if (rules.appFor(sbn.packageName) == null) {
            state.increment(DeviceState.DROPPED_TODAY)
            return
        }
        val now = System.currentTimeMillis()
        when (val decision = filterNotification(NotificationReader.read(sbn), rules, dedupe, now)) {
            is Decision.Drop -> when (decision.reason) {
                DropReason.OTP -> state.increment(DeviceState.OTP_BLOCKED_TODAY)
                DropReason.NOT_LISTENED -> state.increment(DeviceState.DROPPED_TODAY)
                else -> Unit
            }
            is Decision.Keep -> {
                val id = UUID.randomUUID().toString()
                EventQueue.get(context).add(QueuedEvent(id, toEventJson(id, decision.event).toString()), now)
                state.lastEventAt = now
                UploadScheduler.enqueue(context)
            }
        }
    }

    companion object {
        private val worker = Executors.newSingleThreadExecutor()
        private val dedupe = DedupeCache()
        private val ZONE: ZoneId = ZoneId.of("Asia/Ho_Chi_Minh")

        private fun iso(millis: Long): String =
            OffsetDateTime.ofInstant(Instant.ofEpochMilli(millis), ZONE).format(DateTimeFormatter.ISO_OFFSET_DATE_TIME)

        /** Một phần tử của `events` (hợp đồng mục 5 bảng việc); `text` null khi nội dung bị ẩn. */
        fun toEventJson(clientEventId: String, event: NotificationEvent): JSONObject {
            val messages = JSONArray(event.messages.map {
                JSONObject().put("sender", it.sender ?: JSONObject.NULL).put("text", it.text ?: JSONObject.NULL).put("at", iso(it.atMillis))
            })
            val payload = JSONObject()
                .put("title", event.title ?: JSONObject.NULL)
                .put("text", event.text ?: JSONObject.NULL)
                .put("conversation_title", event.conversationTitle ?: JSONObject.NULL)
                .put("messages", messages)
                .put("is_group_conversation", event.isGroupConversation)
                .put("category", event.category ?: JSONObject.NULL)
                .put("notification_key_hash", event.notificationKeyHash)
                .put("hidden_content", event.hiddenContent)
            return JSONObject()
                .put("client_event_id", clientEventId)
                .put("kind", "notification")
                .put("app_package", event.packageName)
                .put("posted_at", iso(event.postedAtMillis))
                .put("payload", payload)
        }
    }
}
