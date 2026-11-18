package vn.io.baohuynh.troly.secure

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Cất mã làm mới và mã thiết bị (30-app-android.md mục 3.5). Khóa AES-256-GCM sinh trong AndroidKeyStore,
 * không ra khỏi kho, không gắn xác thực người dùng để việc nền chạy được khi màn hình khóa.
 * Bản mã (iv:ciphertext, base64) nằm trong SharedPreferences riêng; allowBackup=false.
 * Dùng chung cho SecurePlugin (giao diện) và UploadWorker (gửi sự kiện bằng mã thiết bị).
 */
object SecureStore {
    const val REFRESH_TOKEN = "refresh_token"
    const val DEVICE_TOKEN = "device_token"
    val ALLOWED_KEYS = setOf(REFRESH_TOKEN, DEVICE_TOKEN)

    private const val PREFS = "troly_secure"
    private const val KEY_ALIAS = "troly_secure_key"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"

    private fun prefs(context: Context): SharedPreferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    @Synchronized
    fun get(context: Context, key: String): String? {
        val stored = prefs(context).getString(key, null) ?: return null
        return try {
            decrypt(stored)
        } catch (error: Exception) {
            // Khóa hỏng hoặc dữ liệu cũ không giải được: xóa để app đăng nhập lại thay vì kẹt.
            prefs(context).edit().remove(key).apply()
            null
        }
    }

    @Synchronized
    fun set(context: Context, key: String, value: String) {
        prefs(context).edit().putString(key, encrypt(value)).apply()
    }

    @Synchronized
    fun remove(context: Context, key: String) {
        prefs(context).edit().remove(key).apply()
    }

    @Synchronized
    fun clear(context: Context) {
        prefs(context).edit().clear().apply()
    }

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keyStore.getEntry(KEY_ALIAS, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build(),
        )
        return generator.generateKey()
    }

    private fun encrypt(plain: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        val cipherText = cipher.doFinal(plain.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(cipher.iv, Base64.NO_WRAP) + ":" + Base64.encodeToString(cipherText, Base64.NO_WRAP)
    }

    private fun decrypt(stored: String): String {
        val parts = stored.split(":", limit = 2)
        require(parts.size == 2) { "Dữ liệu cất sai dạng." }
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP)))
        return String(cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)), Charsets.UTF_8)
    }
}
