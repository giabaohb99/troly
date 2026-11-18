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

/**
 * Tải GET /calendar/reminders?days=14 bằng mã thiết bị (If-None-Match, 304 khi không đổi) rồi đặt lại báo thức.
 * Chạy mỗi giờ, khi mở app, khi quay lại tiền cảnh, ngay sau khi sửa lịch hoặc việc (30 mục 3.9).
 */
class ReminderSyncWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result {
        val api = DeviceApi(applicationContext)
        if (!api.hasToken()) return Result.success()
        val store = ReminderStore(applicationContext)
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
            DeviceSync.handleRevoked(applicationContext, result) -> {
                store.clear()
                ReminderScheduler.apply(applicationContext, now)
                return Result.failure()
            }
            result.status == 0 || result.status >= 500 || result.status == 429 -> return Result.retry()
        }
        ReminderScheduler.apply(applicationContext, now)
        return Result.success()
    }

    companion object {
        const val DAYS = 14
    }
}

object ReminderSync {
    private val network = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

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
