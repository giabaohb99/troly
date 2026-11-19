package vn.io.baohuynh.troly.alarm

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ChatDoneFilterTest {
    private val now = 1_800_000_000_000L
    private val minute = 60_000L

    @Test
    fun foregroundNeverShows() {
        assertFalse(ChatDoneFilter.shouldShow(foreground = true, alreadySeen = false, createdAtMillis = now, now = now, inBurst = true))
    }

    @Test
    fun seenInAppNeverShows() {
        assertFalse(ChatDoneFilter.shouldShow(foreground = false, alreadySeen = true, createdAtMillis = now, now = now, inBurst = true))
    }

    @Test
    fun olderThanFifteenMinutesDropped() {
        assertTrue(ChatDoneFilter.shouldShow(false, false, now - 14 * minute, now, inBurst = false))
        assertFalse(ChatDoneFilter.shouldShow(false, false, now - 16 * minute, now, inBurst = true))
    }

    @Test
    fun withoutTimestampOnlyDuringBurst() {
        assertTrue(ChatDoneFilter.shouldShow(false, false, null, now, inBurst = true))
        assertFalse(ChatDoneFilter.shouldShow(false, false, null, now, inBurst = false))
    }
}
