package vn.io.baohuynh.troly.alarm

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
import vn.io.baohuynh.troly.queue.DeviceApi
import vn.io.baohuynh.troly.queue.DeviceSync
import java.util.concurrent.TimeUnit

/** Kết quả một lần tải nhắc. */
enum class SyncOutcome { OK, RETRY, REVOKED }

/**
 * Tải GET /calendar/reminders?days=14 bằng mã thiết bị (If-None-Match, 304 khi không đổi) rồi đặt lại báo thức.
 * Khi app đang mở (sau lượt chat có công cụ, khi quay lại tiền cảnh, sau khi sửa lịch, việc) chạy thẳng trên luồng
 * phụ để nhắc chỉ còn vài phút cũng kịp đặt; WorkManager mỗi giờ và khi lỗi mạng (30 mục 3.9).
 */
class ReminderSyncWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result = when (ReminderSync.fetchAndApply(applicationContext)) {
        SyncOutcome.OK -> Result.success()
        SyncOutcome.RETRY -> Result.retry()
        SyncOutcome.REVOKED -> Result.failure()
    }
}

object ReminderSync {
    const val DAYS = 14
    private val network = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

    @Synchronized
    fun fetchAndApply(context: Context): SyncOutcome {
        val api = DeviceApi(context)
        if (!api.hasToken()) return SyncOutcome.OK
        val store = ReminderStore(context)
        val tag = store.etag ?: store.revision
        val headers = tag?.let { mapOf("If-None-Match" to it) } ?: emptyMap()
        val result = api.request("GET", "/calendar/reminders?days=$DAYS", headers = headers)
        val now = System.currentTimeMillis()
        when {
            result.status == 304 -> store.lastSyncAt = now
            result.status == 200 -> {
                val data = result.data
                val items = data?.optJSONArray("items")
                if (data != null && items != null) store.replaceItems(items, data.optString("revision").takeIf { it.isNotEmpty() }, result.header("ETag"), now)
            }
            DeviceSync.handleRevoked(context, result) -> {
                store.clear()
                ReminderScheduler.apply(context, now)
                return SyncOutcome.REVOKED
            }
            result.status == 0 || result.status >= 500 || result.status == 429 -> return SyncOutcome.RETRY
        }
        ReminderScheduler.apply(context, now)
        return SyncOutcome.OK
    }

    fun schedulePeriodic(context: Context) {
        val request = PeriodicWorkRequestBuilder<ReminderSyncWorker>(1, TimeUnit.HOURS).setConstraints(network).build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork("reminder-sync", ExistingPeriodicWorkPolicy.KEEP, request)
    }

    fun syncNow(context: Context) {
        val request = OneTimeWorkRequestBuilder<ReminderSyncWorker>()
            .setConstraints(network)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("reminder-sync-now", ExistingWorkPolicy.REPLACE, request)
    }
}
