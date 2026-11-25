package vn.io.baohuynh.troly.update

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

class ApkCheckTest {
    // sha256 của chuỗi "abc".
    private val abc = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    @Test
    fun copyHashesAndCopiesBytes() {
        val out = ByteArrayOutputStream()
        val sha = ApkCheck.copyWithHash(ByteArrayInputStream("abc".toByteArray()), out, 3, 100) { _, _ -> }
        assertEquals(abc, sha)
        assertEquals("abc", out.toString())
    }

    @Test
    fun progressOnlyWhenPercentChanges() {
        val data = ByteArray(1024 * 1024)
        val seen = mutableListOf<Int>()
        ApkCheck.copyWithHash(ByteArrayInputStream(data), ByteArrayOutputStream(), data.size.toLong(), Long.MAX_VALUE) { _, p -> seen.add(p) }
        assertEquals(seen.distinct(), seen)
        assertEquals(100, seen.last())
        assertTrue(seen.size <= 101)
    }

    @Test(expected = ApkCheck.TooLargeException::class)
    fun stopsWhenTooLarge() {
        ApkCheck.copyWithHash(ByteArrayInputStream(ByteArray(2000)), ByteArrayOutputStream(), 0, 1000) { _, _ -> }
    }

    @Test
    fun shaMatchIgnoresCaseAndSpaces() {
        assertTrue(ApkCheck.sha256Matches(" ${abc.uppercase()} ", abc))
        assertFalse(ApkCheck.sha256Matches(null, abc))
        assertFalse(ApkCheck.sha256Matches("", abc))
        assertFalse(ApkCheck.sha256Matches(abc.dropLast(1) + "0", abc))
    }

    @Test
    fun verdictChecksShaThenPackage() {
        assertNull(ApkCheck.verdict(abc, abc, "vn.io.baohuynh.troly", "vn.io.baohuynh.troly"))
        assertEquals("sha", ApkCheck.verdict("0".repeat(64), abc, "vn.io.baohuynh.troly", "vn.io.baohuynh.troly"))
        assertEquals("package", ApkCheck.verdict(abc, abc, "vn.io.baohuynh.troly.debug", "vn.io.baohuynh.troly"))
        assertEquals("package", ApkCheck.verdict(abc, abc, null, "vn.io.baohuynh.troly"))
    }

    @Test
    fun percentAndFileName() {
        assertEquals(-1, ApkCheck.percent(10, 0))
        assertEquals(50, ApkCheck.percent(5, 10))
        assertEquals(100, ApkCheck.percent(12, 10))
        assertEquals("troly-110.apk", ApkCheck.fileName(110))
    }
}
