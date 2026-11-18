package vn.io.baohuynh.troly.alarm

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Danh sách nhắc đã tải và trạng thái từng nhắc trên máy (SharedPreferences, không chứa bí mật).
 * [handled]: đã bấm Xong hoặc Đã biết; [fired]: đã hiện thông báo; [snoozed]: giờ kêu mới sau Hoãn.
 */
class ReminderStore(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("troly_reminders", Context.MODE_PRIVATE)

    var revision: String?
        get() = prefs.getString(KEY_REVISION, null)
        set(value) = prefs.edit().putString(KEY_REVISION, value).apply()

    var etag: String?
        get() = prefs.getString(KEY_ETAG, null)
        set(value) = prefs.edit().putString(KEY_ETAG, value).apply()

    var lastSyncAt: Long
        get() = prefs.getLong(KEY_LAST_SYNC, 0)
        set(value) = prefs.edit().putLong(KEY_LAST_SYNC, value).apply()

    var scheduledKeys: Set<String>
        get() = prefs.getStringSet(KEY_SCHEDULED, emptySet()).orEmpty().toSet()
        set(value) = prefs.edit().putStringSet(KEY_SCHEDULED, value).apply()

    val items: List<Reminder> get() = parseItems(prefs.getString(KEY_ITEMS, null))

    val handled: Set<String> get() = prefs.getStringSet(KEY_HANDLED, emptySet()).orEmpty().toSet()

    val fired: Set<String> get() = prefs.getStringSet(KEY_FIRED, emptySet()).orEmpty().toSet()

    val snoozed: Map<String, Long>
        get() {
            val raw = prefs.getString(KEY_SNOOZED, null) ?: return emptyMap()
            val json = runCatching { JSONObject(raw) }.getOrNull() ?: return emptyMap()
            return json.keys().asSequence().associateWith { json.getLong(it) }
        }

    fun find(key: String): Reminder? = items.firstOrNull { it.key == key }

    /** Lưu danh sách mới; bỏ trạng thái của nhắc không còn trong danh sách. */
    @Synchronized
    fun replaceItems(rawItems: JSONArray, revision: String?, etag: String?, now: Long) {
        val keys = parseItems(rawItems.toString()).map { it.key }.toSet()
        val snoozed = snoozed.filterKeys { it in keys }
        prefs.edit()
            .putString(KEY_ITEMS, rawItems.toString())
            .putString(KEY_REVISION, revision)
            .putString(KEY_ETAG, etag)
            .putLong(KEY_LAST_SYNC, now)
            .putStringSet(KEY_HANDLED, handled.filter { it in keys }.toSet())
            .putStringSet(KEY_FIRED, fired.filter { it in keys }.toSet())
            .putString(KEY_SNOOZED, JSONObject(snoozed as Map<*, *>).toString())
            .apply()
    }

    @Synchronized
    fun markHandled(key: String) {
        prefs.edit().putStringSet(KEY_HANDLED, handled + key).apply()
    }

    @Synchronized
    fun markFired(key: String) {
        prefs.edit().putStringSet(KEY_FIRED, fired + key).apply()
    }

    @Synchronized
    fun snooze(key: String, until: Long) {
        val next = snoozed + (key to until)
        prefs.edit()
            .putString(KEY_SNOOZED, JSONObject(next as Map<*, *>).toString())
            .putStringSet(KEY_FIRED, fired - key)
            .apply()
    }

    /** Bỏ danh sách và trạng thái; giữ scheduledKeys để lần apply sau hủy đúng các báo thức đã đặt. */
    fun clear() {
        val scheduled = scheduledKeys
        prefs.edit().clear().putStringSet(KEY_SCHEDULED, scheduled).apply()
    }

    companion object {
        private const val KEY_ITEMS = "items"
        private const val KEY_REVISION = "revision"
        private const val KEY_ETAG = "etag"
        private const val KEY_LAST_SYNC = "last_sync_at"
        private const val KEY_SCHEDULED = "scheduled_keys"
        private const val KEY_HANDLED = "handled"
        private const val KEY_FIRED = "fired"
        private const val KEY_SNOOZED = "snoozed"

        /** Đọc `items` của /calendar/reminders; dòng thiếu khóa hoặc giờ sai thì bỏ. */
        fun parseItems(raw: String?): List<Reminder> {
            if (raw.isNullOrBlank()) return emptyList()
            val array = runCatching { JSONArray(raw) }.getOrNull() ?: return emptyList()
            return (0 until array.length()).mapNotNull { index ->
                val item = array.optJSONObject(index) ?: return@mapNotNull null
                val key = item.optString("reminder_key").takeIf { it.isNotEmpty() } ?: return@mapNotNull null
                val fireAt = ReminderPlan.parseInstant(item.optString("fire_at")) ?: return@mapNotNull null
                Reminder(
                    key = key,
                    source = item.optString("source", "event"),
                    sourceId = if (item.isNull("source_id")) null else item.opt("source_id")?.toString(),
                    fireAt = fireAt,
                    title = item.optString("title").ifEmpty { "Nhắc" },
                    body = if (item.isNull("body")) null else item.optString("body").takeIf { it.isNotEmpty() },
                    kind = item.optString("kind", "normal"),
                    deepLink = if (item.isNull("deep_link")) null else item.optString("deep_link"),
                )
            }
        }
    }
}
