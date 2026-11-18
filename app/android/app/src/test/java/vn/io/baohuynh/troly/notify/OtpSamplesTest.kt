package vn.io.baohuynh.troly.notify

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.yaml.snakeyaml.Yaml
import java.io.File

/**
 * Chạy bộ mẫu chung testdata/otp-samples.yaml (cùng tệp với bài kiểm Python của máy chủ).
 * Hai lớp phải cho cùng kết quả trên mọi mẫu (60 mục 3.5).
 */
class OtpSamplesTest {
    private fun loadSamples(): List<Map<String, Any?>> {
        val dir = System.getProperty("troly.testdata") ?: error("Thiếu thuộc tính troly.testdata (đặt trong app/build.gradle).")
        val file = File(dir, "otp-samples.yaml")
        assertTrue("Không thấy ${file.absolutePath}; khi build trong Docker cần gắn testdata/ vào /testdata", file.exists())
        @Suppress("UNCHECKED_CAST")
        return Yaml().load<List<Map<String, Any?>>>(file.readText())
    }

    @Test
    fun everySampleMatchesExpectation() {
        val samples = loadSamples()
        assertTrue("Bộ mẫu rỗng", samples.isNotEmpty())
        val wrong = samples.filter { sample ->
            val blocked = OtpDetector.containsOtp(
                title = sample["title"] as String?,
                texts = listOf(sample["text"] as String?),
                packageName = sample["package"] as String,
                smsPackage = "com.samsung.android.messaging",
            )
            blocked != (sample["expect"] == "block")
        }.map { "${it["id"]} (cần ${it["expect"]})" }
        assertEquals("Mẫu cho kết quả sai: $wrong", emptyList<String>(), wrong)
    }

    @Test
    fun foldRemovesVietnameseMarks() {
        assertEquals("ma xac thuc dang nhap", OtpDetector.fold("Mã Xác Thực Đăng Nhập"))
    }
}
