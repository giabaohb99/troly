package vn.io.baohuynh.troly.plugin

import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import vn.io.baohuynh.troly.notify.DeviceState
import vn.io.baohuynh.troly.queue.DeviceApi
import vn.io.baohuynh.troly.queue.EventQueue
import vn.io.baohuynh.troly.queue.UploadScheduler
import vn.io.baohuynh.troly.system.PermissionStatus
import java.util.concurrent.Executors

/** Giao diện gọi qua src/core/native/notify.ts (30 mục 3.4). */
@CapacitorPlugin(name = "Notify")
class NotifyPlugin : Plugin() {
    private val io = Executors.newSingleThreadExecutor()

    override fun load() {
        UploadScheduler.schedulePeriodicSync(context)
    }

    @PluginMethod
    fun getStatus(call: PluginCall) {
        io.execute {
            val state = DeviceState(context)
            val permissions = PermissionStatus.read(context)
            call.resolve(
                JSObject()
                    .put("listenerGranted", permissions.notificationListener)
                    .put("listenerConnected", state.listenerConnected)
                    .put("lastEventAt", state.lastEventAt.takeIf { it > 0 })
                    .put("queueSize", EventQueue.get(context).size())
                    .put("droppedToday", state.count(DeviceState.DROPPED_TODAY))
                    .put("otpBlockedToday", state.count(DeviceState.OTP_BLOCKED_TODAY))
                    .put("otpRejectedByServer", state.otpRejectedByServer)
                    .put("deviceRegistered", DeviceApi(context).hasToken())
                    .put("deviceRevoked", state.deviceRevoked)
                    .put("configRevision", state.configRevision),
            )
        }
    }

    /** Gửi ngay hàng đợi (mở app, bấm Gửi ngay ở Kiểm tra máy). */
    @PluginMethod
    fun flushQueue(call: PluginCall) {
        UploadScheduler.enqueue(context)
        call.resolve()
    }

    /** Nhịp tim, tải lại danh sách app được nghe, rồi gửi hàng đợi. */
    @PluginMethod
    fun sync(call: PluginCall) {
        UploadScheduler.syncNow(context)
        call.resolve()
    }
}
