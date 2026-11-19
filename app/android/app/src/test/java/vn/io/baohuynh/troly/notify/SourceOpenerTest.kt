package vn.io.baohuynh.troly.notify

import org.junit.Assert.assertEquals
import org.junit.Test

class SourceOpenerTest {
    @Test
    fun foldIgnoresMarksCaseAndSpaces() {
        assertEquals("chi lan", SourceOpener.fold("  Chị   Lan "))
        assertEquals("nhom du an a", SourceOpener.fold("Nhóm Dự án A"))
        assertEquals("", SourceOpener.fold(null))
    }

    @Test
    fun picksNewestMatchByTitleOrConversation() {
        val candidates = listOf(
            listOf("Anh Hùng", null) to 100L,
            listOf("Tuấn", "Nhóm Dự án A") to 300L,
            listOf("Chị Lan", null) to 200L,
            listOf("chi lan", null) to 250L,
        )
        assertEquals(3, SourceOpener.pickMatch(candidates, listOf("Chị Lan", null)))
        assertEquals(1, SourceOpener.pickMatch(candidates, listOf("Nhóm dự án A", "Tuấn")))
        assertEquals(-1, SourceOpener.pickMatch(candidates, listOf("Mẹ")))
        assertEquals(-1, SourceOpener.pickMatch(candidates, listOf(null, " ")))
    }
}
