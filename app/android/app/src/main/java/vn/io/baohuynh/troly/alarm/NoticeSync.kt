package vn.io.baohuynh.troly.alarm

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import vn.io.baohuynh.troly.queue.DeviceApi
import java.util.concurrent.TimeUnit

/**
 * Thông báo do máy chủ báo (QĐ-38): giao dịch mới vừa ghi, tin quan trọng. Không có đẩy (FCM) nên máy hỏi
 * GET /device/notices?after=<con trỏ> mỗi 15 phút và khoảng 1 phút sau khi gửi lô sự kiện. Máy chủ đã lọc theo
 * công tắc ở Cài đặt, Thông báo. Chưa có đường này (404) thì bỏ qua.
 */
class NoticeWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result {
        val api = DeviceApi(applicationContext)
        if (!api.hasToken()) return Result.success()
        val prefs = NotifyPrefs(applicationContext)
        val after = prefs.noticeCursor
        val result = api.request("GET", "/device/notices" + (after?.let { "?after=$it" } ?: ""))
        if (result.status == 0 || result.status >= 500 || result.status == 429) return Result.retry()
        if (result.status != 200) return Result.success()
        val data = result.data ?: return Result.success()
        val items = data.optJSONArray("items")
        var chatDone = false
        val remaining = inputData.getInt(KEY_REMAINING, 0)
        val inBurst = inputData.keyValueMap.containsKey(KEY_REMAINING)
        val foreground = ChatDoneFilter.isAppForeground(applicationContext)
        val now = System.currentTimeMillis()
        // Lần đầu chỉ lấy con trỏ, không báo dồn tin cũ.
        if (after != null && items != null) {
            for (i in 0 until items.length()) {
                val item = items.optJSONObject(i) ?: continue
                if (item.optString("kind") == "chat_done") {
                    chatDone = true
                    val messageId = item.optString("message_id").ifEmpty { item.optString("id").removePrefix("chat:") }
                    val createdAt = ReminderPlan.parseInstant(item.optString("created_at").takeIf { it.isNotEmpty() })
                    val prefs = NotifyPrefs(applicationContext)
                    if (!ChatDoneFilter.shouldShow(foreground, prefs.isChatNotified(messageId), createdAt, now, inBurst)) {
                        // Đang ở màn hình, đã đọc trong app, hoặc quá cũ: đánh dấu đã xem để không báo về sau.
                        prefs.markChatNotified(messageId)
                        continue
                    }
                    val link = item.optString("deep_link").ifEmpty { "troly://" }
                    val fileId = item.optJSONArray("file_ids")?.optLong(0)?.takeIf { it > 0 }
                        ?: item.optLong("file_id").takeIf { it > 0 }
                    ReminderNotifier.showChatDone(
                        applicationContext,
                        messageId,
                        link,
                        item.optString("body").takeIf { it.isNotEmpty() },
                        fileId?.let { appendQuery(link, "mo-tep=$it") },
                        item.optString("title").takeIf { it.isNotEmpty() },
                    )
                    continue
                }
                if (item.optString("kind") == "booking_added") {
                    ReminderNotifier.showBookingAdded(
                        applicationContext,
                        item.optString("id"),
                        item.optString("title").ifEmpty { "Đã thêm đặt chỗ vào Lịch" },
                        item.optString("body").takeIf { it.isNotEmpty() },
                        item.optString("deep_link").takeIf { it.isNotEmpty() },
                        item.optLong("booking_id"),
                    )
                    continue
                }
                val channel = when (item.optString("kind")) {
                    "transaction" -> ReminderNotifier.CHANNEL_TRANSACTION
                    "important_message" -> ReminderNotifier.CHANNEL_IMPORTANT
                    else -> continue
                }
                ReminderNotifier.showNotice(
                    applicationContext,
                    item.optString("id"),
                    channel,
                    item.optString("title").ifEmpty { "Trợ lý" },
                    item.optString("body").takeIf { it.isNotEmpty() },
                    item.optString("deep_link").takeIf { it.isNotEmpty() },
                )
            }
        }
        data.optString("cursor").takeIf { it.isNotEmpty() }?.let { prefs.noticeCursor = it }
        // Hỏi dồn sau khi gửi tin lúc chạy nền: còn lượt và chưa thấy chat_done thì hỏi tiếp sau 20 giây.
        if (remaining > 0 && !chatDone) NoticeSync.burst(applicationContext, remaining - 1)
        return Result.success()
    }

    companion object {
        const val KEY_REMAINING = "remaining"

        fun appendQuery(link: String, query: String): String = if ('?' in link) "$link&$query" else "$link?$query"
    }
}

object NoticeSync {
    private val network = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

    fun schedulePeriodic(context: Context) {
        val request = PeriodicWorkRequestBuilder<NoticeWorker>(15, TimeUnit.MINUTES).setConstraints(network).build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork("device-notices", ExistingPeriodicWorkPolicy.KEEP, request)
    }

    /**
     * Gửi tin rồi app chạy nền (QĐ-41): hỏi /device/notices khoảng 20 giây một lần, tối đa 15 lần (khoảng 5 phút),
     * dừng khi thấy chat_done.
     */
    fun burst(context: Context, remaining: Int = 15) {
        if (remaining <= 0) return
        val request = OneTimeWorkRequestBuilder<NoticeWorker>()
            .setConstraints(network)
            .setInitialDelay(20, TimeUnit.SECONDS)
            .setInputData(workDataOf(NoticeWorker.KEY_REMAINING to remaining))
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("device-notices-burst", ExistingWorkPolicy.APPEND_OR_REPLACE, request)
    }

    /** Sau khi gửi lô sự kiện: máy chủ xử lý nền vài chục giây rồi mới có thông báo. */
    fun checkSoon(context: Context) {
        val request = OneTimeWorkRequestBuilder<NoticeWorker>().setConstraints(network).setInitialDelay(60, TimeUnit.SECONDS).build()
        WorkManager.getInstance(context).enqueueUniqueWork("device-notices-soon", ExistingWorkPolicy.REPLACE, request)
    }
}
