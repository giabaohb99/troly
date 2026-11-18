package vn.io.baohuynh.troly.alarm

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ReminderPlanTest {
    private val now = 1_800_000_000_000L
    private val minute = 60_000L

    private fun reminder(key: String, fireAt: Long, kind: String = "normal", source: String = "event") =
        Reminder(key, source, "1", fireAt, "Họp", null, kind, "troly://lich/su-kien/1")

    @Test
    fun scheduleOnlyFutureSortedByTime() {
        val plan = ReminderPlan.compute(
            listOf(reminder("b", now + 30 * minute), reminder("a", now + 5 * minute, kind = "alarm"), reminder("old", now - 60 * minute)),
            emptyMap(), emptySet(), emptySet(), now,
        )
        assertEquals(listOf("a", "b"), plan.schedule.map { it.key })
        assertTrue(plan.schedule.first().isAlarm)
        assertTrue(plan.fireNow.isEmpty())
    }

    @Test
    fun handledNeverRings() {
        val plan = ReminderPlan.compute(listOf(reminder("a", now + minute), reminder("b", now - minute)), emptyMap(), setOf("a", "b"), emptySet(), now)
        assertTrue(plan.schedule.isEmpty())
        assertTrue(plan.fireNow.isEmpty())
    }

    @Test
    fun snoozeMovesFireTime() {
        val plan = ReminderPlan.compute(listOf(reminder("a", now - 2 * minute)), mapOf("a" to now + 8 * minute), emptySet(), setOf("a"), now)
        assertEquals(now + 8 * minute, plan.schedule.single().fireAt)
    }

    @Test
    fun missedWithinGraceFiresOnceAfterReboot() {
        val items = listOf(reminder("a", now - 10 * minute), reminder("b", now - 20 * minute))
        assertEquals(listOf("a"), ReminderPlan.compute(items, emptyMap(), emptySet(), emptySet(), now).fireNow)
        assertTrue(ReminderPlan.compute(items, emptyMap(), emptySet(), setOf("a"), now).fireNow.isEmpty())
    }

    @Test
    fun capAtMaxAlarms() {
        val items = (1..500).map { reminder("k$it", now + it * minute) }
        val plan = ReminderPlan.compute(items, emptyMap(), emptySet(), emptySet(), now)
        assertEquals(ReminderPlan.MAX_ALARMS, plan.schedule.size)
        assertEquals("k1", plan.schedule.first().key)
    }

    @Test
    fun parseInstantAcceptsUtcAndOffset() {
        assertEquals(ReminderPlan.parseInstant("2026-11-18T02:00:00Z"), ReminderPlan.parseInstant("2026-11-18T09:00:00+07:00"))
        assertNull(ReminderPlan.parseInstant("hôm nay"))
        assertNull(ReminderPlan.parseInstant(null))
    }

    @Test
    fun deepLinkOnlyOwnScheme() {
        assertEquals("troly://lich/viec/5", ReminderPlan.safeDeepLink("troly://lich/viec/5"))
        assertNull(ReminderPlan.safeDeepLink("https://evil.example/x"))
        assertNull(ReminderPlan.safeDeepLink("intent://x"))
    }
}
