package vn.io.baohuynh.troly.notify

import java.security.MessageDigest

/** Dữ liệu đọc từ một thông báo, đã tách khỏi lớp Android để kiểm bằng JUnit. */
data class NotificationInput(
    val packageName: String,
    val postedAtMillis: Long,
    val key: String,
    val title: String?,
    val text: String?,
    val conversationTitle: String?,
    val messages: List<NotificationMessage>,
    val isGroupConversation: Boolean,
    val category: String?,
    val ongoing: Boolean,
    val foregroundService: Boolean,
    val groupSummary: Boolean,
    val hasProgress: Boolean,
)

data class NotificationMessage(val sender: String?, val text: String?, val atMillis: Long)

/** Một dòng của tab_listened_app; `sms_default` là dòng đặc biệt, thay bằng gói SMS mặc định thật. */
data class ListenedApp(val packageName: String, val purpose: String, val enabled: Boolean)

data class FilterRules(
    val ownPackage: String,
    val apps: List<ListenedApp>,
    val defaultSmsPackage: String?,
    val brandSenders: Collection<String> = OtpDetector.DEFAULT_SMS_BRAND_SENDERS,
) {
    /** Dòng đang bật ứng với gói, hoặc null nếu gói không được nghe. */
    fun appFor(packageName: String): ListenedApp? =
        apps.firstOrNull { it.enabled && it.packageName == packageName }
            ?: apps.firstOrNull { it.enabled && it.packageName == SMS_DEFAULT && packageName == defaultSmsPackage }

    companion object {
        const val SMS_DEFAULT = "sms_default"
    }
}

/** Sự kiện sẽ gửi lên `POST /device/events` (hợp đồng ở mục 5 bảng việc, 30 mục 3.8). */
data class NotificationEvent(
    val packageName: String,
    val postedAtMillis: Long,
    val title: String?,
    val text: String?,
    val conversationTitle: String?,
    val messages: List<NotificationMessage>,
    val isGroupConversation: Boolean,
    val category: String?,
    val notificationKeyHash: String,
    val hiddenContent: Boolean,
)

enum class DropReason { NOT_LISTENED, OWN_APP, ONGOING, GROUP_SUMMARY, EMPTY_EXPENSE, OTP, DUPLICATE }

sealed class Decision {
    data class Drop(val reason: DropReason) : Decision()
    data class Keep(val event: NotificationEvent) : Decision()
}

const val MAX_TEXT_CHARS = 2000

private val PROGRESS_CATEGORIES = setOf("progress", "call", "transport", "service", "navigation")
private val CONTROL_CHARS = Regex("[\\u0000-\\u0008\\u000B\\u000C\\u000E-\\u001F\\u007F]")

fun sha256Hex(text: String): String =
    MessageDigest.getInstance("SHA-256").digest(text.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }

private fun clean(text: String?): String? =
    text?.let { CONTROL_CHARS.replace(it, "").trim().take(MAX_TEXT_CHARS) }?.takeIf { it.isNotEmpty() }

/**
 * Bộ lọc trên máy (30 mục 3.7), theo thứ tự; gặp điều kiện bỏ là dừng. Gói ngoài danh sách bị bỏ
 * trước khi đọc bất cứ trường nào khác. Hàm thuần; [dedupe] giữ trạng thái chống trùng.
 */
fun filterNotification(input: NotificationInput, rules: FilterRules, dedupe: DedupeCache, nowMillis: Long): Decision {
    val app = rules.appFor(input.packageName) ?: return Decision.Drop(DropReason.NOT_LISTENED)
    if (input.packageName == rules.ownPackage) return Decision.Drop(DropReason.OWN_APP)
    if (input.ongoing || input.foregroundService || input.hasProgress || input.category in PROGRESS_CATEGORIES) {
        return Decision.Drop(DropReason.ONGOING)
    }
    if (input.groupSummary) return Decision.Drop(DropReason.GROUP_SUMMARY)

    val title = clean(input.title)
    val text = clean(input.text)
    val conversationTitle = clean(input.conversationTitle)
    val keyHash = sha256Hex(input.key)
    // Zalo, Messenger chồng tin trên cùng một thông báo: chỉ lấy tin mới hơn tin cuối đã gửi.
    val newMessages = dedupe.newMessages(keyHash, input.messages.mapNotNull { m ->
        clean(m.text)?.let { NotificationMessage(clean(m.sender), it, m.atMillis) }
    })
    val isExpense = app.purpose == "expense"
    val empty = text == null && newMessages.isEmpty()

    if (isExpense && empty) return Decision.Drop(DropReason.EMPTY_EXPENSE)
    val texts = listOf(text, conversationTitle) + newMessages.flatMap { listOf(it.sender, it.text) }
    if (OtpDetector.containsOtp(title, texts, input.packageName, rules.defaultSmsPackage, isExpense, rules.brandSenders)) {
        return Decision.Drop(DropReason.OTP)
    }
    if (input.messages.isNotEmpty() && newMessages.isEmpty()) return Decision.Drop(DropReason.DUPLICATE)
    if (!dedupe.markSeen(sha256Hex("${input.packageName}\n${title ?: ""}\n${text ?: ""}"), nowMillis)) {
        return Decision.Drop(DropReason.DUPLICATE)
    }
    dedupe.advanceCursor(keyHash, newMessages)

    return Decision.Keep(
        NotificationEvent(
            packageName = input.packageName,
            postedAtMillis = input.postedAtMillis,
            title = title,
            text = text,
            conversationTitle = conversationTitle,
            messages = newMessages,
            isGroupConversation = input.isGroupConversation,
            category = input.category,
            notificationKeyHash = keyHash,
            hiddenContent = empty,
        ),
    )
}
