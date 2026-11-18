package vn.io.baohuynh.troly.queue

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONArray
import org.json.JSONObject
import vn.io.baohuynh.troly.alarm.NoticeSync
import vn.io.baohuynh.troly.notify.DeviceState
import java.util.concurrent.TimeUnit

/**
 * Gửi hàng đợi lên POST /device/events theo lô (30 mục 3.8, hợp đồng mục 5 bảng việc).
 * accepted + duplicates + rejected bằng số đã gửi: xóa cả lô. Lỗi mạng, 5xx, 429: giữ lô, thử lại sau.
 * 401 DEVICE_REVOKED: dừng hẳn. 426: giữ hàng đợi, chờ cập nhật app.
 */
class UploadWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result {
        val api = DeviceApi(applicationContext)
        if (!api.hasToken()) return Result.success()
        val queue = EventQueue.get(applicationContext)
        val state = DeviceState(applicationContext)
        repeat(MAX_BATCHES_PER_RUN) {
            val batch = queue.take(state.batchMax)
            if (batch.isEmpty()) return Result.success()
            val events = JSONArray(batch.map { JSONObject(it.body) })
            val result = api.request("POST", "/device/events", JSONObject().put("events", events))
            when {
                result.status in 200..299 -> {
                    val rejected = result.data?.optJSONArray("rejected")
                    val otp = (0 until (rejected?.length() ?: 0)).count { rejected!!.getJSONObject(it).optString("code") == "OTP_DETECTED" }
                    if (otp > 0) state.otpRejectedByServer = state.otpRejectedByServer + otp
                    queue.delete(batch.map { it.clientEventId })
                    // Máy chủ có thể vừa ghi giao dịch hoặc gặp tin quan trọng: hỏi thông báo sau ít phút.
                    NoticeSync.checkSoon(applicationContext)
                }
                result.status == 0 || result.status >= 500 || result.status == 429 -> return Result.retry()
                DeviceSync.handleRevoked(applicationContext, result) -> return Result.failure()
                result.status == 426 || result.status == 401 -> return Result.failure()
                // Lô sai dạng (400, 413): bỏ lô để hàng đợi không kẹt mãi.
                else -> queue.delete(batch.map { it.clientEventId })
            }
        }
        // Còn nhiều: xếp lượt sau.
        UploadScheduler.enqueue(applicationContext)
        return Result.success()
    }

    companion object {
        private const val MAX_BATCHES_PER_RUN = 20
    }
}

/** Nhịp tim, tải cấu hình, gửi phần còn trong hàng đợi; chạy 6 giờ một lần và khi mở app. */
class SyncWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result {
        if (!DeviceSync.run(applicationContext)) return Result.failure()
        UploadScheduler.enqueue(applicationContext)
        return Result.success()
    }
}

object UploadScheduler {
    private val network = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

    fun enqueue(context: Context) {
        val request = OneTimeWorkRequestBuilder<UploadWorker>()
            .setConstraints(network)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        // APPEND_OR_REPLACE: sự kiện đến khi việc đang chạy vẫn có lượt gửi kế tiếp.
        WorkManager.getInstance(context).enqueueUniqueWork("upload-events", ExistingWorkPolicy.APPEND_OR_REPLACE, request)
    }

    fun schedulePeriodicSync(context: Context) {
        val request = PeriodicWorkRequestBuilder<SyncWorker>(6, TimeUnit.HOURS).setConstraints(network).build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork("device-sync", ExistingPeriodicWorkPolicy.KEEP, request)
    }

    fun syncNow(context: Context) {
        val request = OneTimeWorkRequestBuilder<SyncWorker>().setConstraints(network).build()
        WorkManager.getInstance(context).enqueueUniqueWork("device-sync-now", ExistingWorkPolicy.REPLACE, request)
    }
}
