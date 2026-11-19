package vn.io.baohuynh.troly.alarm

import android.app.ActivityManager
import android.content.Context
import vn.io.baohuynh.troly.plugin.AlarmPlugin

/**
 * Chốt chặn notice chat_done ở máy (lỗi 1.0.2: đang chat vẫn nhận 4 thông báo *Trợ lý đã trả lời*):
 * app ở tiền cảnh thì không phát; tin đã nhận trọn trong app hoặc đã báo thì bỏ; notice cũ hơn 15 phút thì bỏ.
 * Máy chủ chưa gửi created_at thì chỉ phát trong lượt hỏi dày sau khi gửi tin lúc chạy nền.
 */
object ChatDoneFilter {
    const val MAX_AGE_MILLIS = 15L * 60_000

    fun shouldShow(foreground: Boolean, alreadySeen: Boolean, createdAtMillis: Long?, now: Long, inBurst: Boolean): Boolean {
        if (foreground || alreadySeen) return false
        if (createdAtMillis == null) return inBurst
        return now - createdAtMillis <= MAX_AGE_MILLIS
    }

    /** App đang ở màn hình: cờ của plugin hoặc mức ưu tiên tiến trình (khi plugin chưa kịp nhận onResume). */
    fun isAppForeground(context: Context): Boolean {
        if (AlarmPlugin.isAppVisible) return true
        val info = ActivityManager.RunningAppProcessInfo()
        ActivityManager.getMyMemoryState(info)
        return info.importance <= ActivityManager.RunningAppProcessInfo.IMPORTANCE_FOREGROUND
    }
}
