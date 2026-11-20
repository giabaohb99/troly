package vn.io.baohuynh.troly.voice

/**
 * Câu báo lỗi tiếng Việt cho nhận giọng nói và đọc trả lời (30 mục 3.4, plugin Voice). Mã lỗi là hằng của
 * android.speech.SpeechRecognizer, viết số để kiểm bằng JUnit không cần Android.
 */
object VoiceText {
    const val MIC_DENIED = "Chưa cho phép dùng micro. Mở Cài đặt máy > Ứng dụng > Trợ lý > Quyền để bật micro."
    const val NO_RECOGNIZER = "Máy chưa có dịch vụ nhận giọng nói. Bật app Google (hoặc Samsung Voice) rồi thử lại."
    const val TTS_NO_VI = "Máy chưa có giọng đọc tiếng Việt. Mở cài đặt giọng đọc để tải giọng tiếng Việt."
    const val TTS_UNAVAILABLE = "Máy chưa có bộ đọc văn bản (Text-to-speech)."

    /** Tên mã gửi giao diện, để giao diện xử lý riêng (ví dụ mở cài đặt) mà không dựa vào câu chữ. */
    fun code(error: Int): String = when (error) {
        1, 2 -> "NETWORK" // ERROR_NETWORK_TIMEOUT, ERROR_NETWORK
        3 -> "AUDIO"
        4 -> "SERVER"
        5 -> "CLIENT"
        6 -> "NO_SPEECH" // ERROR_SPEECH_TIMEOUT
        7 -> "NO_MATCH"
        8 -> "BUSY"
        9 -> "MIC_DENIED" // ERROR_INSUFFICIENT_PERMISSIONS
        10 -> "TOO_MANY_REQUESTS"
        11 -> "SERVER_DISCONNECTED"
        12, 13 -> "LANGUAGE" // ERROR_LANGUAGE_NOT_SUPPORTED, ERROR_LANGUAGE_UNAVAILABLE
        else -> "UNKNOWN"
    }

    fun message(error: Int): String = when (code(error)) {
        "NETWORK", "SERVER", "SERVER_DISCONNECTED" -> "Không có mạng hoặc mạng yếu, nhận giọng nói chưa được. Thử lại khi có sóng."
        "AUDIO" -> "Không mở được micro. App khác có thể đang dùng micro."
        "NO_SPEECH", "NO_MATCH" -> "Em chưa nghe thấy gì, bấm micro rồi nói lại nhé."
        "BUSY", "TOO_MANY_REQUESTS" -> "Micro đang bận, thử lại sau giây lát."
        "MIC_DENIED" -> MIC_DENIED
        "LANGUAGE" -> "Máy chưa có gói tiếng Việt cho nhận giọng nói. Tải tiếng Việt trong cài đặt giọng nói của Google."
        "CLIENT" -> "Nhận giọng nói bị dừng, bấm micro để nói lại."
        else -> "Lỗi nhận giọng nói (mã $error)."
    }

    /** Kết quả TextToSpeech.setLanguage: từ 0 trở lên (LANG_AVAILABLE...) là đọc được; -1 thiếu dữ liệu, -2 không hỗ trợ. */
    fun ttsLanguageUsable(result: Int): Boolean = result >= 0
}
