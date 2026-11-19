package vn.io.baohuynh.troly.plugin

import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import android.content.Intent
import android.os.Build
import android.provider.Settings
import vn.io.baohuynh.troly.alarm.NoticeSync
import vn.io.baohuynh.troly.alarm.NotifyPrefs
import vn.io.baohuynh.troly.alarm.Reminder
import vn.io.baohuynh.troly.alarm.ReminderNotifier
import vn.io.baohuynh.troly.alarm.ReminderPlan
import vn.io.baohuynh.troly.alarm.ReminderScheduler
import vn.io.baohuynh.troly.alarm.ReminderStore
import vn.io.baohuynh.troly.alarm.ReminderSync
import vn.io.baohuynh.troly.alarm.SyncOutcome
import java.lang.ref.WeakReference
import java.util.concurrent.Executors

/** Giao diện gọi qua src/core/native/alarm.ts (30 mục 3.4). Danh sách nhắc do lớp gốc tự tải bằng mã thiết bị. */
@CapacitorPlugin(name = "Alarm")
class AlarmPlugin : Plugin() {
    private val io = Executors.newSingleThreadExecutor()

    override fun load() {
        instance = WeakReference(this)
        ReminderNotifier.ensureChannels(context)
        ReminderSync.schedulePeriodic(context)
        NoticeSync.schedulePeriodic(context)
        // Android 15 hủy mọi PendingIntent khi người dùng buộc dừng app: mở app là đặt lại.
        io.execute { ReminderScheduler.apply(context) }
    }

    /**
     * Tải lại nhắc ngay (mở app, quay lại tiền cảnh, sau lượt chat có công cụ, sau khi sửa lịch hoặc việc).
     * Chạy thẳng trên luồng phụ để nhắc chỉ còn vài phút cũng kịp đặt; lỗi mạng thì giao WorkManager thử lại.
     */
    @PluginMethod
    fun sync(call: PluginCall) {
        io.execute {
            val outcome = ReminderSync.fetchAndApply(context)
            if (outcome == SyncOutcome.RETRY) ReminderSync.syncNow(context)
            call.resolve(JSObject().put("outcome", outcome.name.lowercase()))
        }
    }

    /** Cài đặt thông báo lưu trên máy (QĐ-38). */
    @PluginMethod
    fun getNotifyPrefs(call: PluginCall) {
        val prefs = NotifyPrefs(context)
        call.resolve(JSObject().put("sound", prefs.sound).put("quietStart", prefs.quietStart).put("quietEnd", prefs.quietEnd).put("chatDone", prefs.chatDone))
    }

    @PluginMethod
    fun setNotifyPrefs(call: PluginCall) {
        val prefs = NotifyPrefs(context)
        call.getBoolean("sound")?.let { prefs.sound = it }
        call.getBoolean("chatDone")?.let { prefs.chatDone = it }
        if (call.data.has("quietStart")) prefs.quietStart = call.getString("quietStart")?.takeIf { it.matches(HHMM) }
        if (call.data.has("quietEnd")) prefs.quietEnd = call.getString("quietEnd")?.takeIf { it.matches(HHMM) }
        call.resolve()
    }

    // App đang ở màn hình hay không, cho NoticeWorker bỏ notice chat_done khi người dùng đang xem (QĐ-41).
    override fun handleOnResume() {
        super.handleOnResume()
        isAppVisible = true
    }

    override fun handleOnPause() {
        super.handleOnPause()
        isAppVisible = false
    }

    /** App còn sống mà không ở màn hình lúc lượt chat xong: tự báo ngay (QĐ-41). */
    @PluginMethod
    fun notifyChatDone(call: PluginCall) {
        val messageId = call.getString("messageId") ?: return call.reject("Thiếu messageId.")
        val deepLink = call.getString("deepLink") ?: "troly://"
        ReminderNotifier.showChatDone(context, messageId, deepLink, call.getString("body"), call.getString("fileLink"))
        call.resolve()
    }

    /** Tin đã nhận trọn trong app (stream xong, hoặc đã tải trong màn chat): notice chat_done của nó bị bỏ. */
    @PluginMethod
    fun markChatSeen(call: PluginCall) {
        val ids = call.getArray("messageIds")?.toList<Any>().orEmpty()
        val prefs = NotifyPrefs(context)
        ids.forEach { prefs.markChatNotified(it.toString()) }
        call.resolve()
    }

    /** Gửi tin rồi rời app: hỏi notice dày hơn trong vài phút phòng khi WebView bị dừng. */
    @PluginMethod
    fun startNoticeBurst(call: PluginCall) {
        NoticeSync.burst(context)
        call.resolve()
    }

    /** Mở trang cài đặt của một kênh thông báo để chỉnh âm thanh, rung (Android 8 trở lên). */
    @PluginMethod
    fun openChannelSettings(call: PluginCall) {
        ReminderNotifier.ensureChannels(context)
        val channel = call.getString("channel")
        val intent = if (channel != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS)
                .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
                .putExtra(Settings.EXTRA_CHANNEL_ID, channel)
        } else {
            Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
        }
        try {
            activity.startActivity(intent)
            call.resolve(JSObject().put("opened", true))
        } catch (_: Exception) {
            call.resolve(JSObject().put("opened", false))
        }
    }

    @PluginMethod
    fun getScheduled(call: PluginCall) {
        io.execute {
            val store = ReminderStore(context)
            val items = store.items.associateBy { it.key }
            val plan = ReminderPlan.compute(store.items, store.snoozed, store.handled, store.fired, System.currentTimeMillis())
            val next = JSArray()
            plan.schedule.take(3).forEach { alarm ->
                next.put(
                    JSObject()
                        .put("key", alarm.key)
                        .put("title", items[alarm.key]?.title ?: "")
                        .put("fireAt", alarm.fireAt)
                        .put("kind", if (alarm.isAlarm) "alarm" else "normal"),
                )
            }
            call.resolve(
                JSObject()
                    .put("count", plan.schedule.size)
                    .put("revision", store.revision)
                    .put("lastSyncAt", store.lastSyncAt.takeIf { it > 0 })
                    .put("exactAllowed", ReminderScheduler.canScheduleExact(context))
                    .put("next", next),
            )
        }
    }

    @PluginMethod
    fun canScheduleExact(call: PluginCall) {
        call.resolve(JSObject().put("value", ReminderScheduler.canScheduleExact(context)))
    }

    private fun emit(reminder: Reminder, action: String) {
        notifyListeners(
            "reminderAction",
            JSObject().put("key", reminder.key).put("source", reminder.source).put("sourceId", reminder.sourceId).put("action", action),
        )
    }

    companion object {
        @Volatile private var instance: WeakReference<AlarmPlugin>? = null

        @Volatile var isAppVisible: Boolean = false
            private set
        private val HHMM = Regex("""^([01]\d|2[0-3]):[0-5]\d$""")

        /** Báo giao diện (nếu đang mở) để tải lại màn Lịch sau khi bấm nút trên thông báo. */
        fun emitAction(reminder: Reminder, action: String) {
            instance?.get()?.emit(reminder, action)
        }
    }
}
