package vn.io.baohuynh.troly.alarm

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalTime

class NotifyPrefsTest {
    private fun at(value: String) = LocalTime.parse(value)

    @Test
    fun quietHoursAcrossMidnight() {
        assertTrue(NotifyPrefs.inQuietHours("22:00", "07:00", at("23:30")))
        assertTrue(NotifyPrefs.inQuietHours("22:00", "07:00", at("06:59")))
        assertFalse(NotifyPrefs.inQuietHours("22:00", "07:00", at("07:00")))
        assertFalse(NotifyPrefs.inQuietHours("22:00", "07:00", at("12:00")))
    }

    @Test
    fun quietHoursSameDay() {
        assertTrue(NotifyPrefs.inQuietHours("12:00", "13:30", at("12:45")))
        assertFalse(NotifyPrefs.inQuietHours("12:00", "13:30", at("13:30")))
    }

    @Test
    fun offOrInvalidMeansNoQuiet() {
        assertFalse(NotifyPrefs.inQuietHours(null, "07:00", at("03:00")))
        assertFalse(NotifyPrefs.inQuietHours("25:00", "07:00", at("03:00")))
        assertFalse(NotifyPrefs.inQuietHours("08:00", "08:00", at("08:00")))
    }
}
