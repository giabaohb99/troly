package vn.io.baohuynh.troly.alarm

import java.time.Instant
import java.time.OffsetDateTime

/** Một nhắc từ GET /calendar/reminders (12 mục 5.5). [fireAt] là mili giây epoch. */
data class Reminder(
    val key: String,
    val source: String,
    val sourceId: String?,
    val fireAt: Long,
    val title: String,
    val body: String?,
    val kind: String,
    val deepLink: String?,
) {
    val isAlarm: Boolean get() = kind == "alarm"
    val isTask: Boolean get() = source == "task"
}

data class ScheduledAlarm(val key: String, val fireAt: Long, val isAlarm: Boolean)

/** Việc cần làm với AlarmManager: đặt [schedule], hiện ngay [fireNow] (lỡ giờ do máy tắt, chưa quá [MISSED_GRACE_MILLIS]). */
data class AlarmPlan(val schedule: List<ScheduledAlarm>, val fireNow: List<String>)

/**
 * Tính lịch báo thức từ danh sách nhắc, phần hoãn và phần đã xử lý (30 mục 3.9). Thuần Kotlin để kiểm bằng JUnit.
 * Bấm Xong hoặc Đã biết thì không kêu lại; Hoãn thì dời giờ kêu; nhắc đã qua giờ không kêu bù sau 15 phút.
 */
object ReminderPlan {
    const val MISSED_GRACE_MILLIS = 15L * 60_000
    const val SNOOZE_MILLIS = 10L * 60_000

    /** Android giới hạn 500 báo thức mỗi app; giữ dưới mốc này. */
    const val MAX_ALARMS = 400

    fun compute(
        items: List<Reminder>,
        snoozed: Map<String, Long>,
        handled: Set<String>,
        fired: Set<String>,
        now: Long,
    ): AlarmPlan {
        val schedule = mutableListOf<ScheduledAlarm>()
        val fireNow = mutableListOf<String>()
        for (item in items) {
            if (item.key in handled) continue
            val at = snoozed[item.key] ?: item.fireAt
            when {
                at > now -> schedule += ScheduledAlarm(item.key, at, item.isAlarm)
                now - at <= MISSED_GRACE_MILLIS && item.key !in fired -> fireNow += item.key
            }
        }
        return AlarmPlan(schedule.sortedBy { it.fireAt }.take(MAX_ALARMS), fireNow)
    }

    /** Giờ ISO có múi (Z hoặc +07:00) sang mili giây; sai dạng trả null. */
    fun parseInstant(value: String?): Long? {
        if (value.isNullOrBlank()) return null
        return runCatching { OffsetDateTime.parse(value).toInstant().toEpochMilli() }
            .recoverCatching { Instant.parse(value).toEpochMilli() }
            .getOrNull()
    }

    /** Chỉ mở đường dẫn sâu của chính app. */
    fun safeDeepLink(value: String?): String? = value?.takeIf { it.startsWith("troly://") }
}
