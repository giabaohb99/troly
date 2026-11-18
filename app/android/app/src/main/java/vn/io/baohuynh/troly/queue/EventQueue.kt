package vn.io.baohuynh.troly.queue

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

/** Một sự kiện chờ gửi: [body] là JSON của đúng một phần tử trong `events` của POST /device/events. */
data class QueuedEvent(val clientEventId: String, val body: String)

/**
 * Hàng đợi sự kiện trên máy (30 mục 3.8). Dùng SQLiteOpenHelper thay Room cho gọn (không cần sinh mã).
 * Giữ tối đa 7 ngày hoặc 5.000 dòng, khớp mốc EVENT_TOO_OLD của máy chủ.
 */
class EventQueue private constructor(context: Context) :
    SQLiteOpenHelper(context.applicationContext, "troly_queue.db", null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            "CREATE TABLE device_event_queue (client_event_id TEXT PRIMARY KEY, body TEXT NOT NULL, created_at INTEGER NOT NULL)",
        )
        db.execSQL("CREATE INDEX ix_queue_created ON device_event_queue (created_at)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit

    @Synchronized
    fun add(event: QueuedEvent, nowMillis: Long = System.currentTimeMillis()) {
        val db = writableDatabase
        db.insertWithOnConflict(
            "device_event_queue",
            null,
            ContentValues().apply {
                put("client_event_id", event.clientEventId)
                put("body", event.body)
                put("created_at", nowMillis)
            },
            SQLiteDatabase.CONFLICT_IGNORE,
        )
        db.delete("device_event_queue", "created_at < ?", arrayOf((nowMillis - MAX_AGE_MILLIS).toString()))
        db.execSQL(
            "DELETE FROM device_event_queue WHERE client_event_id NOT IN " +
                "(SELECT client_event_id FROM device_event_queue ORDER BY created_at DESC LIMIT $MAX_ROWS)",
        )
    }

    /** Lấy một lô theo thứ tự cũ trước, không quá [limit] sự kiện và [maxBytes] byte. */
    @Synchronized
    fun take(limit: Int, maxBytes: Int = MAX_BATCH_BYTES): List<QueuedEvent> {
        val result = mutableListOf<QueuedEvent>()
        var bytes = 32
        readableDatabase.rawQuery(
            "SELECT client_event_id, body FROM device_event_queue ORDER BY created_at LIMIT ?",
            arrayOf(limit.toString()),
        ).use { cursor ->
            while (cursor.moveToNext()) {
                val body = cursor.getString(1)
                val size = body.toByteArray(Charsets.UTF_8).size + 1
                if (result.isNotEmpty() && bytes + size > maxBytes) break
                bytes += size
                result += QueuedEvent(cursor.getString(0), body)
            }
        }
        return result
    }

    @Synchronized
    fun delete(ids: Collection<String>) {
        if (ids.isEmpty()) return
        val db = writableDatabase
        db.beginTransaction()
        try {
            for (id in ids) db.delete("device_event_queue", "client_event_id = ?", arrayOf(id))
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    @Synchronized
    fun size(): Int = readableDatabase.rawQuery("SELECT COUNT(*) FROM device_event_queue", null).use { c ->
        if (c.moveToFirst()) c.getInt(0) else 0
    }

    companion object {
        const val MAX_AGE_MILLIS = 7L * 24 * 3_600_000
        const val MAX_ROWS = 5_000
        const val MAX_BATCH_BYTES = 250_000

        @Volatile private var instance: EventQueue? = null

        fun get(context: Context): EventQueue =
            instance ?: synchronized(this) { instance ?: EventQueue(context).also { instance = it } }
    }
}
