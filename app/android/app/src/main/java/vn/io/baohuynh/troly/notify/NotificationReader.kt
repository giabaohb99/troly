package vn.io.baohuynh.troly.notify

import android.app.Notification
import android.service.notification.StatusBarNotification
import androidx.core.app.NotificationCompat

/**
 * Đọc các trường cần thiết từ một thông báo (30 mục 3.6). Chỉ gọi sau khi gói đã qua bước 1 của bộ lọc,
 * để thông báo của app không được nghe không bị đọc nội dung.
 */
object NotificationReader {
    fun read(sbn: StatusBarNotification): NotificationInput {
        val notification = sbn.notification
        val extras = notification.extras
        val bigText = extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString()
        val text = bigText?.takeIf { it.isNotBlank() } ?: extras.getCharSequence(Notification.EXTRA_TEXT)?.toString()
        val style = NotificationCompat.MessagingStyle.extractMessagingStyleFromNotification(notification)
        val messages = style?.messages.orEmpty().map { message ->
            NotificationMessage(message.person?.name?.toString(), message.text?.toString(), message.timestamp)
        }
        val progressMax = extras.getInt(Notification.EXTRA_PROGRESS_MAX, 0)
        val indeterminate = extras.getBoolean(Notification.EXTRA_PROGRESS_INDETERMINATE, false)
        return NotificationInput(
            packageName = sbn.packageName,
            postedAtMillis = sbn.postTime,
            key = sbn.key,
            title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString(),
            text = text,
            conversationTitle = style?.conversationTitle?.toString() ?: extras.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE)?.toString(),
            messages = messages,
            isGroupConversation = style?.isGroupConversation ?: extras.getBoolean(Notification.EXTRA_IS_GROUP_CONVERSATION, false),
            category = notification.category,
            ongoing = notification.flags and Notification.FLAG_ONGOING_EVENT != 0,
            foregroundService = notification.flags and Notification.FLAG_FOREGROUND_SERVICE != 0,
            groupSummary = notification.flags and Notification.FLAG_GROUP_SUMMARY != 0,
            hasProgress = progressMax > 0 || indeterminate,
        )
    }
}
