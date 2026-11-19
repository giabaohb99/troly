package vn.io.baohuynh.troly.notify

import android.app.ActivityOptions
import android.app.Notification
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.service.notification.StatusBarNotification
import java.lang.ref.WeakReference
import java.text.Normalizer

/**
 * Mở lại cuộc chat gốc (QĐ-43, Zalo không gửi thay): thông báo gốc còn trên máy thì kích contentIntent của nó (mở
 * đúng cuộc chat), không thì mở app. Khớp theo tên cuộc trò chuyện hoặc người gửi.
 */
object SourceOpener {
    @Volatile private var listener: WeakReference<TrolyNotificationListener>? = null

    fun attach(service: TrolyNotificationListener?) {
        listener = service?.let { WeakReference(it) }
    }

    /** Chữ để so: bỏ dấu, chữ thường, gọn khoảng trắng. */
    fun fold(value: String?): String {
        if (value.isNullOrBlank()) return ""
        val noMarks = Normalizer.normalize(value, Normalizer.Form.NFD).replace(Regex("\\p{M}+"), "")
        return noMarks.replace('đ', 'd').replace('Đ', 'D').lowercase().trim().replace(Regex("\\s+"), " ")
    }

    /** Chọn thông báo khớp mới nhất trong danh sách (tên, giờ đăng). Trả chỉ số hoặc -1. Thuần để kiểm JUnit. */
    fun pickMatch(candidates: List<Pair<List<String?>, Long>>, titles: List<String?>): Int {
        val wanted = titles.map(::fold).filter { it.isNotEmpty() }.toSet()
        if (wanted.isEmpty()) return -1
        var best = -1
        var bestTime = Long.MIN_VALUE
        candidates.forEachIndexed { index, (names, postedAt) ->
            if (names.any { fold(it) in wanted } && postedAt > bestTime) {
                best = index
                bestTime = postedAt
            }
        }
        return best
    }

    /** Trả "notification" khi mở được qua thông báo gốc, "app" khi mở app, null khi không mở được. */
    fun open(context: Context, packageName: String, titles: List<String?>): String? {
        val active: List<StatusBarNotification> = runCatching { listener?.get()?.activeNotifications?.toList() }.getOrNull().orEmpty()
            .filter { it.packageName == packageName && it.notification.contentIntent != null }
        val index = pickMatch(
            active.map { sbn ->
                val extras = sbn.notification.extras
                listOf(extras.getCharSequence(Notification.EXTRA_TITLE)?.toString(), extras.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE)?.toString()) to sbn.postTime
            },
            titles,
        )
        if (index >= 0 && send(active[index].notification.contentIntent)) return "notification"
        val launch = context.packageManager.getLaunchIntentForPackage(packageName)?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK) ?: return null
        return runCatching { context.startActivity(launch) }.map { "app" }.getOrNull()
    }

    private fun send(intent: PendingIntent): Boolean = runCatching {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            // Android 14 trở lên: app đang ở màn hình cho phép PendingIntent của Zalo mở màn chat.
            val options = ActivityOptions.makeBasic().setPendingIntentBackgroundActivityStartMode(ActivityOptions.MODE_BACKGROUND_ACTIVITY_START_ALLOWED)
            intent.send(null, 0, null, null, null, null, options.toBundle())
        } else {
            intent.send()
        }
    }.isSuccess
}
