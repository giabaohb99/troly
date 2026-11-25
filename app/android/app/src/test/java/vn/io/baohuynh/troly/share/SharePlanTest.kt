package vn.io.baohuynh.troly.share

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SharePlanTest {
    @Test
    fun acceptsImagesAndReadableFiles() {
        assertTrue(SharePlan.accepts("image/jpeg", "a.jpg"))
        assertTrue(SharePlan.accepts("application/pdf", null))
        assertTrue(SharePlan.accepts("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "hd.docx"))
        assertTrue(SharePlan.accepts("application/octet-stream", "ghi-chu.md"))
        assertTrue(SharePlan.accepts(null, "bao-cao.PDF"))
        assertFalse(SharePlan.accepts("video/mp4", "clip.mp4"))
        assertFalse(SharePlan.accepts("application/zip", "a.zip"))
        assertFalse(SharePlan.accepts("application/octet-stream", "a.exe"))
    }

    @Test
    fun safeNameStripsPathsAndKeepsExtension() {
        assertEquals("hop-dong.pdf", SharePlan.safeName("../../sdcard/hop-dong.pdf", "pdf"))
        assertEquals("a_b.jpg", SharePlan.safeName("a:b.jpg", "jpg"))
        assertEquals("tep-chia-se.png", SharePlan.safeName(null, "png"))
        val long = SharePlan.safeName("x".repeat(200) + ".docx", "docx")
        assertEquals(120, long.length)
        assertTrue(long.endsWith(".docx"))
    }

    @Test
    fun sharedTextJoinsSubject() {
        assertEquals("Hợp đồng\nhttps://x.vn/a", SharePlan.sharedText("https://x.vn/a", "Hợp đồng"))
        assertEquals("Bài báo hay https://x.vn", SharePlan.sharedText("Bài báo hay https://x.vn", "Bài báo hay"))
        assertNull(SharePlan.sharedText("  ", null))
    }
}
