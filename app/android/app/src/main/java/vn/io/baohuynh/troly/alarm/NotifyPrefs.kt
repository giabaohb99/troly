package vn.io.baohuynh.troly.alarm

import android.content.Context
import java.time.LocalTime
import java.time.ZoneId

/**
 * Cài đặt thông báo lưu trên máy (QĐ-38): kêu và rung, giờ yên lặng. Giờ yên lặng chỉ làm thông báo im tiếng,
 * vẫn hiện; nhắc kiểu báo thức (chỉ khi người dùng bảo đặt báo thức, QĐ-39) luôn kêu.
 */
class NotifyPrefs(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("troly_notify", Context.MODE_PRIVATE)

    var sound: Boolean
        get() = prefs.getBoolean(KEY_SOUND, true)
        set(value) = prefs.edit().putBoolean(KEY_SOUND, value).apply()

    /** "HH:MM" hoặc null khi tắt giờ yên lặng. */
    var quietStart: String?
        get() = prefs.getString(KEY_QUIET_START, null)
        set(value) = prefs.edit().putString(KEY_QUIET_START, value).apply()

    var quietEnd: String?
        get() = prefs.getString(KEY_QUIET_END, null)
        set(value) = prefs.edit().putString(KEY_QUIET_END, value).apply()

    /** Báo khi trợ lý trả lời lúc app không ở màn hình (QĐ-41). */
    var chatDone: Boolean
        get() = prefs.getBoolean(KEY_CHAT_DONE, true)
        set(value) = prefs.edit().putBoolean(KEY_CHAT_DONE, value).apply()

    fun isChatNotified(messageId: String): Boolean =
        messageId in prefs.getString(KEY_CHAT_SEEN, "").orEmpty().split(',')

    /** Đánh dấu đã báo tin [messageId]; trả false nếu đã báo rồi (app tự báo và notice máy chủ không báo hai lần). */
    @Synchronized
    fun markChatNotified(messageId: String): Boolean {
        val seen = prefs.getString(KEY_CHAT_SEEN, "").orEmpty().split(',').filter { it.isNotEmpty() }
        if (messageId in seen) return false
        prefs.edit().putString(KEY_CHAT_SEEN, (seen + messageId).takeLast(200).joinToString(",")).apply()
        return true
    }

    var noticeCursor: String?
        get() = prefs.getString(KEY_NOTICE_CURSOR, null)
        set(value) = prefs.edit().putString(KEY_NOTICE_CURSOR, value).apply()

    /** Thông báo thường có nên im tiếng lúc [now] không. */
    fun shouldSilence(now: LocalTime = LocalTime.now(ZONE)): Boolean = !sound || inQuietHours(quietStart, quietEnd, now)

    companion object {
        private const val KEY_SOUND = "sound"
        private const val KEY_QUIET_START = "quiet_start"
        private const val KEY_QUIET_END = "quiet_end"
        private const val KEY_NOTICE_CURSOR = "notice_cursor"
        private const val KEY_CHAT_DONE = "chat_done"
        private const val KEY_CHAT_SEEN = "chat_seen"
        private val ZONE: ZoneId = ZoneId.of("Asia/Ho_Chi_Minh")

        /** Khung có thể qua nửa đêm (22:00 tới 07:00). Giờ sai dạng coi như không có giờ yên lặng. */
        fun inQuietHours(start: String?, end: String?, now: LocalTime): Boolean {
            val from = start?.let { runCatching { LocalTime.parse(it) }.getOrNull() } ?: return false
            val to = end?.let { runCatching { LocalTime.parse(it) }.getOrNull() } ?: return false
            if (from == to) return false
            return if (from < to) now >= from && now < to else now >= from || now < to
        }
    }
}
