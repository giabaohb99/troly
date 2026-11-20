package vn.io.baohuynh.troly.alarm

import org.junit.Assert.assertEquals
import org.junit.Test

class BookingUndoPlanTest {
    @Test
    fun doneOnSuccessOrAlreadyGone() {
        assertEquals(UndoOutcome.Done, BookingUndoPlan.outcome(200, null))
        assertEquals(UndoOutcome.Done, BookingUndoPlan.outcome(404, "Không tìm thấy"))
    }

    @Test
    fun retriesOnNetworkAndServerErrors() {
        assertEquals(UndoOutcome.Retry, BookingUndoPlan.outcome(0, null))
        assertEquals(UndoOutcome.Retry, BookingUndoPlan.outcome(503, null))
        assertEquals(UndoOutcome.Retry, BookingUndoPlan.outcome(429, null))
    }

    @Test
    fun showsServerMessageWhenRefused() {
        assertEquals(UndoOutcome.Failed("Sự kiện đã sửa trên Lịch, xóa tay nếu cần."), BookingUndoPlan.outcome(409, "Sự kiện đã sửa trên Lịch, xóa tay nếu cần."))
        assertEquals(UndoOutcome.Failed("Không hoàn tác được, mở Lịch để xóa tay."), BookingUndoPlan.outcome(400, " "))
    }

    @Test
    fun sameNotificationIdAsTheNotice() {
        assertEquals(("notice:b-7").hashCode(), BookingUndoPlan.notificationId("b-7"))
    }

    @Test
    fun undoneTextFromTitle() {
        assertEquals("Đã bỏ đặt phòng Hotel X, 21–22/11 khỏi Lịch", BookingUndoPlan.undoneText("Đã thêm đặt phòng Hotel X, 21–22/11 vào Lịch"))
        assertEquals("Đã bỏ đặt chỗ khỏi Lịch", BookingUndoPlan.undoneText(""))
    }
}
