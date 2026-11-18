package vn.io.baohuynh.troly.notify

/**
 * Chống trùng trên máy (30 mục 3.7 bước 6): cùng băm (gói, tiêu đề, chữ) trong 10 phút thì bỏ;
 * tin trong messages[] chỉ lấy tin mới hơn tin cuối đã gửi của cùng thông báo.
 * Giữ trong bộ nhớ của tiến trình; mất khi tiến trình chết thì máy chủ vẫn chống trùng bằng dedupe_hash.
 */
class DedupeCache(
    private val windowMillis: Long = 10 * 60_000L,
    private val maxEntries: Int = 2_000,
) {
    private val seen = LinkedHashMap<String, Long>()
    private val cursors = LinkedHashMap<String, Long>()

    /** Trả false nếu đã thấy trong khung thời gian. */
    @Synchronized
    fun markSeen(hash: String, nowMillis: Long): Boolean {
        val last = seen[hash]
        if (last != null && nowMillis - last < windowMillis) return false
        seen.remove(hash)
        seen[hash] = nowMillis
        trim(seen)
        return true
    }

    @Synchronized
    fun newMessages(keyHash: String, messages: List<NotificationMessage>): List<NotificationMessage> {
        val cursor = cursors[keyHash] ?: Long.MIN_VALUE
        return messages.filter { it.atMillis > cursor }
    }

    @Synchronized
    fun advanceCursor(keyHash: String, sent: List<NotificationMessage>) {
        val latest = sent.maxOfOrNull { it.atMillis } ?: return
        val previous = cursors.remove(keyHash) ?: Long.MIN_VALUE
        cursors[keyHash] = maxOf(latest, previous)
        trim(cursors)
    }

    private fun trim(map: LinkedHashMap<String, Long>) {
        while (map.size > maxEntries) map.remove(map.keys.first())
    }
}
