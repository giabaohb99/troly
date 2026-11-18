package vn.io.baohuynh.troly.notify

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NotificationFilterTest {
    private val rules = FilterRules(
        ownPackage = "vn.io.baohuynh.troly",
        apps = listOf(
            ListenedApp("com.VCB", "expense", true),
            ListenedApp("com.zing.zalo", "inbox", true),
            ListenedApp("org.telegram.messenger", "inbox", false),
            ListenedApp(FilterRules.SMS_DEFAULT, "inbox", true),
        ),
        defaultSmsPackage = "com.samsung.android.messaging",
    )

    private fun input(
        pkg: String = "com.zing.zalo",
        title: String? = "Lan",
        text: String? = "Chiều 3h30 gặp nhé",
        messages: List<NotificationMessage> = emptyList(),
        ongoing: Boolean = false,
        category: String? = null,
        groupSummary: Boolean = false,
        key: String = "0|com.zing.zalo|1|null|10123",
    ) = NotificationInput(pkg, 1_000L, key, title, text, null, messages, false, category, ongoing, false, groupSummary, false)

    private fun drop(decision: Decision) = (decision as? Decision.Drop)?.reason
    private fun keep(decision: Decision) = (decision as Decision.Keep).event

    @Test
    fun dropsPackagesNotListenedOrDisabled() {
        assertEquals(DropReason.NOT_LISTENED, drop(filterNotification(input(pkg = "com.facebook.katana"), rules, DedupeCache(), 0)))
        assertEquals(DropReason.NOT_LISTENED, drop(filterNotification(input(pkg = "org.telegram.messenger"), rules, DedupeCache(), 0)))
    }

    @Test
    fun smsDefaultMapsToRealSmsPackage() {
        val event = keep(filterNotification(input(pkg = "com.samsung.android.messaging", title = "Mẹ", text = "Tối về ăn cơm"), rules, DedupeCache(), 0))
        assertEquals("com.samsung.android.messaging", event.packageName)
        assertEquals(DropReason.NOT_LISTENED, drop(filterNotification(input(pkg = "com.google.android.apps.messaging"), rules, DedupeCache(), 0)))
    }

    @Test
    fun dropsOngoingCallsAndGroupSummaries() {
        assertEquals(DropReason.ONGOING, drop(filterNotification(input(ongoing = true), rules, DedupeCache(), 0)))
        assertEquals(DropReason.ONGOING, drop(filterNotification(input(category = "call"), rules, DedupeCache(), 0)))
        assertEquals(DropReason.GROUP_SUMMARY, drop(filterNotification(input(groupSummary = true), rules, DedupeCache(), 0)))
    }

    @Test
    fun dropsOtpAndBankNoticesWithoutAmount() {
        val otp = input(pkg = "com.samsung.android.messaging", title = "Vietcombank", text = "Ma OTP cua Quy khach la 834512")
        assertEquals(DropReason.OTP, drop(filterNotification(otp, rules, DedupeCache(), 0)))
        val login = input(pkg = "com.VCB", title = "Vietcombank", text = "Thiet bi moi vua dang nhap VCB Digibank")
        assertEquals(DropReason.OTP, drop(filterNotification(login, rules, DedupeCache(), 0)))
    }

    @Test
    fun keepsBankTransactions() {
        val tx = input(pkg = "com.VCB", title = "Vietcombank", text = "So du TK VCB xxxx7890 -120,000 VND luc 18-11-2026 08:15:02.")
        val event = keep(filterNotification(tx, rules, DedupeCache(), 0))
        assertEquals("com.VCB", event.packageName)
        assertEquals(64, event.notificationKeyHash.length)
    }

    @Test
    fun hiddenMessageKeptForInboxDroppedForExpense() {
        val hidden = keep(filterNotification(input(text = null), rules, DedupeCache(), 0))
        assertTrue(hidden.hiddenContent)
        assertNull(hidden.text)
        assertEquals(DropReason.EMPTY_EXPENSE, drop(filterNotification(input(pkg = "com.VCB", text = "  "), rules, DedupeCache(), 0)))
    }

    @Test
    fun duplicatesWithinTenMinutesAreDropped() {
        val cache = DedupeCache()
        keep(filterNotification(input(), rules, cache, 0))
        assertEquals(DropReason.DUPLICATE, drop(filterNotification(input(), rules, cache, 5 * 60_000L)))
        keep(filterNotification(input(), rules, cache, 11 * 60_000L))
    }

    @Test
    fun stackedMessagesOnlySendNewOnes() {
        val cache = DedupeCache()
        val first = listOf(NotificationMessage("Lan", "Chào anh", 100), NotificationMessage("Lan", "Mai họp nhé", 200))
        assertEquals(2, keep(filterNotification(input(messages = first), rules, cache, 0)).messages.size)
        val second = first + NotificationMessage("Lan", "Nhớ mang laptop", 300)
        val event = keep(filterNotification(input(messages = second, text = "Nhớ mang laptop"), rules, cache, 1_000))
        assertEquals(listOf("Nhớ mang laptop"), event.messages.map { it.text })
        assertEquals(DropReason.DUPLICATE, drop(filterNotification(input(messages = second, text = "x"), rules, cache, 2_000)))
    }

    @Test
    fun cutsLongTextAndControlChars() {
        val event = keep(filterNotification(input(text = "a\u0007" + "b".repeat(3000)), rules, DedupeCache(), 0))
        assertEquals(MAX_TEXT_CHARS, event.text!!.length)
        assertTrue(event.text!!.startsWith("ab"))
    }
}
