package vn.io.baohuynh.troly.plugin

import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import vn.io.baohuynh.troly.alarm.Reminder
import vn.io.baohuynh.troly.alarm.ReminderNotifier
import vn.io.baohuynh.troly.alarm.ReminderPlan
import vn.io.baohuynh.troly.alarm.ReminderScheduler
import vn.io.baohuynh.troly.alarm.ReminderStore
import vn.io.baohuynh.troly.alarm.ReminderSync
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
        // Android 15 hủy mọi PendingIntent khi người dùng buộc dừng app: mở app là đặt lại.
        io.execute { ReminderScheduler.apply(context) }
    }

    /** Tải lại nhắc ngay (mở app, quay lại tiền cảnh, sau khi sửa lịch hoặc việc). */
    @PluginMethod
    fun sync(call: PluginCall) {
        ReminderSync.syncNow(context)
        call.resolve()
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

        /** Báo giao diện (nếu đang mở) để tải lại màn Lịch sau khi bấm nút trên thông báo. */
        fun emitAction(reminder: Reminder, action: String) {
            instance?.get()?.emit(reminder, action)
        }
    }
}
