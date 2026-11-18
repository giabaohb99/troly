package vn.io.baohuynh.troly.notify

import java.text.Normalizer
import java.util.Locale

/**
 * Lọc OTP lớp 1 trên điện thoại (60 mục 3.5, QĐ-04). Chép đúng luật của máy chủ
 * backend/app/modules/device/otp.py bản [RULES_VERSION]; đổi luật thì sửa cả hai phía và chạy
 * testdata/otp-samples.yaml ở cả hai. Khớp thì bỏ cả thông báo, không lưu nội dung.
 * Hàm thuần, không đụng Android, kiểm bằng JUnit trên JVM.
 */
object OtpDetector {
    const val RULES_VERSION = "2026-11-18.3"

    private val KEYWORDS = listOf(
        "otp", "smart otp", "ma xac thuc", "ma xac nhan", "ma xac minh", "ma kich hoat", "ma dang nhap",
        "ma bao mat", "mat khau mot lan", "khong cung cap ma", "verification code", "confirmation code",
        "security code", "login code", "passcode", "one-time", "one time", "2fa",
    )

    val DEFAULT_SMS_BRAND_SENDERS = listOf(
        "Vietcombank", "VCB", "Techcombank", "TCB", "MoMo", "ZaloPay", "VNPAY", "MBBank", "VPBank", "ACB", "BIDV",
        "VietinBank", "Agribank", "TPBank", "Sacombank", "Google", "Facebook", "Zalo", "Shopee", "Grab",
    )

    val BANK_PACKAGES = setOf("com.VCB", "vn.com.techcombank.bb.app", "com.mservice.momotransfer")
    val SMS_PACKAGES = setOf("com.samsung.android.messaging", "com.google.android.apps.messaging")

    private val KEYWORD = Regex("(?<![a-z0-9])(?:" + KEYWORDS.joinToString("|") { Regex.escape(it) } + ")(?![a-z0-9])")

    // Mã 4 tới 8 số đứng riêng: không dính ngày, giờ, số tiền có dấu ngăn, mã tham chiếu có dấu chấm.
    private val CODE = Regex("(?<![\\d\\-/:.,])\\d{4,8}(?![\\d\\-/:]|[.,]\\d)")
    private val SPLIT_CODE = Regex("(?<![\\d\\-/:.,])\\d{3}[- ]\\d{3}(?![\\d\\-/:]|[.,]\\d)")
    private val LETTER_CODE = Regex("(?<![a-z0-9])[a-z]-\\d{4,8}(?!\\d)")

    // Dấu hiệu số tiền: có dấu ngăn nghìn hoặc có đơn vị tiền.
    private val AMOUNT = Regex("\\d{1,3}(?:[.,]\\d{3})+|\\d+\\s?(?:vnd|dong|d)(?![a-z])")
    private val MARKS = Regex("\\p{Mn}+")
    private val SPACES = Regex("\\s+")

    /** Bỏ dấu, đổi đ thành d, chữ thường; giống `_fold` của otp.py. */
    fun fold(text: String?): String {
        val replaced = (text ?: "").replace('đ', 'd').replace('Đ', 'd')
        return MARKS.replace(Normalizer.normalize(replaced, Normalizer.Form.NFD), "").lowercase(Locale.ROOT)
    }

    /**
     * @param expenseApp gói có purpose = expense trong danh sách nghe; null thì theo 3 gói mặc định.
     * @param smsPackage gói SMS mặc định thật của máy.
     */
    fun containsOtp(
        title: String?,
        texts: List<String?>,
        packageName: String,
        smsPackage: String? = null,
        expenseApp: Boolean? = null,
        brandSenders: Collection<String> = DEFAULT_SMS_BRAND_SENDERS,
    ): Boolean {
        val folded = fold((listOf(title ?: "") + texts.map { it ?: "" }).joinToString("\n"))
        val isExpense = expenseApp ?: (packageName in BANK_PACKAGES)
        // Theo nguồn: app ngân hàng, ví mà không có số tiền thì bỏ cả tin, có mã hay không.
        if (isExpense && !AMOUNT.containsMatchIn(folded)) return true
        if (LETTER_CODE.containsMatchIn(folded)) return true
        val hasCode = CODE.containsMatchIn(folded) || SPLIT_CODE.containsMatchIn(folded)
        if (!hasCode) return false
        if (KEYWORD.containsMatchIn(folded)) return true
        if (packageName in SMS_PACKAGES || (smsPackage != null && packageName == smsPackage)) {
            val sender = SPACES.replace(fold(title), "")
            val brands = brandSenders.map { SPACES.replace(it.lowercase(Locale.ROOT), "") }.toSet()
            if (sender in brands) return true
        }
        return false
    }
}
