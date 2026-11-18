package vn.io.baohuynh.troly.secure;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * Cất mã làm mới và mã thiết bị (30-app-android.md mục 3.5).
 * Khóa AES-256-GCM sinh trong AndroidKeyStore, không ra khỏi kho; không gắn xác thực người dùng
 * để việc nền chạy được khi màn hình khóa. Bản mã (iv:ciphertext, base64) nằm trong SharedPreferences
 * riêng của app; allowBackup=false nên không vào bản sao lưu.
 * Giao diện gọi qua src/core/native/secure.ts: get, set, remove, clear.
 */
@CapacitorPlugin(name = "Secure")
public class SecurePlugin extends Plugin {

    private static final String PREFS = "troly_secure";
    private static final String KEY_ALIAS = "troly_secure_key";
    private static final String TRANSFORMATION = "AES/GCM/NoPadding";
    private static final Set<String> ALLOWED_KEYS = new HashSet<>(Arrays.asList("refresh_token", "device_token"));

    @PluginMethod
    public void get(PluginCall call) {
        String key = readKey(call);
        if (key == null) return;
        String stored = prefs().getString(key, null);
        JSObject result = new JSObject();
        if (stored == null) {
            result.put("value", JSObject.NULL);
            call.resolve(result);
            return;
        }
        try {
            result.put("value", decrypt(stored));
            call.resolve(result);
        } catch (Exception error) {
            // Khóa hỏng hoặc dữ liệu cũ không giải được: xóa để app đăng nhập lại thay vì kẹt.
            prefs().edit().remove(key).apply();
            result.put("value", JSObject.NULL);
            call.resolve(result);
        }
    }

    @PluginMethod
    public void set(PluginCall call) {
        String key = readKey(call);
        if (key == null) return;
        String value = call.getString("value");
        if (value == null) {
            call.reject("Thiếu giá trị cần cất.");
            return;
        }
        try {
            prefs().edit().putString(key, encrypt(value)).apply();
            call.resolve();
        } catch (Exception error) {
            call.reject("Không cất được mã vào kho khóa.", error);
        }
    }

    @PluginMethod
    public void remove(PluginCall call) {
        String key = readKey(call);
        if (key == null) return;
        prefs().edit().remove(key).apply();
        call.resolve();
    }

    @PluginMethod
    public void clear(PluginCall call) {
        prefs().edit().clear().apply();
        call.resolve();
    }

    private String readKey(PluginCall call) {
        String key = call.getString("key");
        if (key == null || !ALLOWED_KEYS.contains(key)) {
            call.reject("Khóa không hợp lệ.");
            return null;
        }
        return key;
    }

    private SharedPreferences prefs() {
        return getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private SecretKey getOrCreateKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        if (keyStore.containsAlias(KEY_ALIAS)) {
            return ((KeyStore.SecretKeyEntry) keyStore.getEntry(KEY_ALIAS, null)).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(
            new KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        );
        return generator.generateKey();
    }

    private String encrypt(String plain) throws Exception {
        Cipher cipher = Cipher.getInstance(TRANSFORMATION);
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey());
        byte[] cipherText = cipher.doFinal(plain.getBytes(StandardCharsets.UTF_8));
        return Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP) + ":" + Base64.encodeToString(cipherText, Base64.NO_WRAP);
    }

    private String decrypt(String stored) throws Exception {
        String[] parts = stored.split(":", 2);
        if (parts.length != 2) throw new IllegalArgumentException("Dữ liệu cất sai dạng.");
        byte[] iv = Base64.decode(parts[0], Base64.NO_WRAP);
        byte[] cipherText = Base64.decode(parts[1], Base64.NO_WRAP);
        Cipher cipher = Cipher.getInstance(TRANSFORMATION);
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), new GCMParameterSpec(128, iv));
        return new String(cipher.doFinal(cipherText), StandardCharsets.UTF_8);
    }
}
