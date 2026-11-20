package vn.io.baohuynh.troly.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceTextTest {
    @Test
    fun mapsRecognizerErrorsToVietnamese() {
        assertEquals("NETWORK", VoiceText.code(2))
        assertEquals("NETWORK", VoiceText.code(1))
        assertTrue(VoiceText.message(2).startsWith("Không có mạng"))
        assertEquals(VoiceText.MIC_DENIED, VoiceText.message(9))
        assertEquals("Em chưa nghe thấy gì, bấm micro rồi nói lại nhé.", VoiceText.message(7))
        assertEquals(VoiceText.message(7), VoiceText.message(6))
        assertEquals("LANGUAGE", VoiceText.code(12))
        assertEquals("Lỗi nhận giọng nói (mã 99).", VoiceText.message(99))
    }

    @Test
    fun ttsLanguageResult() {
        assertTrue(VoiceText.ttsLanguageUsable(0))
        assertTrue(VoiceText.ttsLanguageUsable(2))
        assertFalse(VoiceText.ttsLanguageUsable(-1))
        assertFalse(VoiceText.ttsLanguageUsable(-2))
    }
}
