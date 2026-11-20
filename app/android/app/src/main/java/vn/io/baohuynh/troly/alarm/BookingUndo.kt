package vn.io.baohuynh.troly.alarm

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import org.json.JSONObject
import vn.io.baohuynh.troly.R
import vn.io.baohuynh.troly.queue.DeviceApi
import vn.io.baohuynh.troly.queue.DeviceSync
import java.util.concurrent.TimeUnit

/** Kết quả gọi hoàn tác đặt chỗ (QĐ-49), tách khỏi Android để kiểm bằng JUnit. */
sealed class UndoOutcome {
    object Done : UndoOutcome()
    object Retry : UndoOutcome()
    data class Failed(val message: String) : UndoOutcome()
}

object BookingUndoPlan {
    /** 2xx hoặc 404 (đặt chỗ đã không còn) là xong; mạng, 5xx, 429 thử lại; còn lại báo câu của máy chủ. */
    fun outcome(status: Int, serverMessage: String?): UndoOutcome = when {
        status in 200..299 || status == 404 -> UndoOutcome.Done
        status == 0 || status >= 500 || status == 429 -> UndoOutcome.Retry
        else -> UndoOutcome.Failed(serverMessage?.takeIf { it.isNotBlank() } ?: "Không hoàn tác được, mở Lịch để xóa tay.")
    }

    fun notificationId(noticeId: String): Int = ("notice:$noticeId").hashCode()

    /** *Đã thêm đặt phòng X, 21–22/11 vào Lịch* thành *Đã bỏ đặt phòng X, 21–22/11 khỏi Lịch*. */
    fun undoneText(title: String): String {
        val core = title.trim().removePrefix("Đã thêm ").removeSuffix(" vào Lịch").trim()
        return if (core.isEmpty()) "Đã bỏ đặt chỗ khỏi Lịch" else "Đã bỏ $core khỏi Lịch"
    }
}

/** Nút Hoàn tác trên thông báo *Đã thêm đặt phòng...*: đổi thông báo thành *Đang hoàn tác* rồi gọi máy chủ khi có mạng. */
class BookingUndoReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val bookingId = intent.getLongExtra(EXTRA_BOOKING_ID, 0).takeIf { it > 0 } ?: return
        val noticeId = intent.getStringExtra(EXTRA_NOTICE_ID) ?: return
        val title = intent.getStringExtra(EXTRA_TITLE).orEmpty()
        BookingUndoWorker.showStatus(context, noticeId, "Đang hoàn tác...", title, ongoing = true)
        val request = OneTimeWorkRequestBuilder<BookingUndoWorker>()
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .setInputData(workDataOf(EXTRA_BOOKING_ID to bookingId, EXTRA_NOTICE_ID to noticeId, EXTRA_TITLE to title))
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("booking-undo-$bookingId", ExistingWorkPolicy.KEEP, request)
    }

    companion object {
        const val ACTION_UNDO = "vn.io.baohuynh.troly.BOOKING_UNDO"
        const val EXTRA_BOOKING_ID = "bookingId"
        const val EXTRA_NOTICE_ID = "noticeId"
        const val EXTRA_TITLE = "title"

        fun undoIntent(context: Context, bookingId: Long, noticeId: String, title: String): PendingIntent {
            val intent = Intent(context, BookingUndoReceiver::class.java)
                .setAction(ACTION_UNDO)
                .putExtra(EXTRA_BOOKING_ID, bookingId)
                .putExtra(EXTRA_NOTICE_ID, noticeId)
                .putExtra(EXTRA_TITLE, title)
            return PendingIntent.getBroadcast(context, "undo:$noticeId".hashCode(), intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        }
    }
}

class BookingUndoWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result {
        val bookingId = inputData.getLong(BookingUndoReceiver.EXTRA_BOOKING_ID, 0)
        val noticeId = inputData.getString(BookingUndoReceiver.EXTRA_NOTICE_ID) ?: return Result.failure()
        val title = inputData.getString(BookingUndoReceiver.EXTRA_TITLE).orEmpty()
        val api = DeviceApi(applicationContext)
        if (!api.hasToken()) return Result.failure()
        val result = api.request("POST", "/device/bookings/$bookingId/undo", JSONObject())
        if (DeviceSync.handleRevoked(applicationContext, result)) return Result.failure()
        return when (val outcome = BookingUndoPlan.outcome(result.status, result.body?.optString("message"))) {
            UndoOutcome.Done -> {
                showStatus(applicationContext, noticeId, "Đã hoàn tác", BookingUndoPlan.undoneText(title), ongoing = false)
                Result.success()
            }
            UndoOutcome.Retry -> Result.retry()
            is UndoOutcome.Failed -> {
                showStatus(applicationContext, noticeId, "Chưa hoàn tác được", outcome.message, ongoing = false)
                Result.success()
            }
        }
    }

    companion object {
        /** Thay nội dung thông báo cũ (cùng id), không kêu lại. */
        fun showStatus(context: Context, noticeId: String, title: String, body: String, ongoing: Boolean) {
            ReminderNotifier.ensureChannels(context)
            val manager = NotificationManagerCompat.from(context)
            if (!manager.areNotificationsEnabled()) return
            val builder = NotificationCompat.Builder(context, ReminderNotifier.CHANNEL_REMINDER)
                .setSmallIcon(R.drawable.ic_stat_reminder)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(NotificationCompat.BigTextStyle().bigText(body))
                .setOnlyAlertOnce(true)
                .setSilent(true)
                .setOngoing(ongoing)
                .setAutoCancel(!ongoing)
            try {
                manager.notify(BookingUndoPlan.notificationId(noticeId), builder.build())
            } catch (_: SecurityException) {
                // Mất quyền thông báo: bỏ qua.
            }
        }
    }
}
