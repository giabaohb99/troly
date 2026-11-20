package vn.io.baohuynh.troly.plugin

import android.Manifest
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import com.getcapacitor.JSObject
import com.getcapacitor.PermissionState
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import com.getcapacitor.annotation.Permission
import com.getcapacitor.annotation.PermissionCallback
import vn.io.baohuynh.troly.voice.VoiceText
import java.util.Locale

/**
 * Nói với trợ lý (30 mục 3.4, bản 1.0.6): nhận giọng bằng SpeechRecognizer của Android (WebView không có Web Speech),
 * tiếng Việt, có kết quả tạm, tự dừng khi im lặng; đọc câu trả lời bằng TextToSpeech tiếng Việt của máy.
 * Sự kiện: `partial` {text}, `final` {text}, `error` {code, message}, `end`, `speakEnd`.
 */
@CapacitorPlugin(
    name = "Voice",
    permissions = [Permission(alias = "microphone", strings = [Manifest.permission.RECORD_AUDIO])],
)
class VoicePlugin : Plugin() {
    private var recognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var ttsReady: Boolean? = null
    private var ttsVietnamese = false
    private val waitingForTts = mutableListOf<() -> Unit>()

    private fun micGranted(): Boolean = getPermissionState("microphone") == PermissionState.GRANTED

    @PluginMethod
    fun isAvailable(call: PluginCall) {
        call.resolve(
            JSObject()
                .put("recognition", SpeechRecognizer.isRecognitionAvailable(context))
                .put("micGranted", micGranted()),
        )
    }

    @PluginMethod
    fun start(call: PluginCall) {
        if (!micGranted()) {
            requestPermissionForAlias("microphone", call, "micCallback")
            return
        }
        begin(call)
    }

    @PermissionCallback
    private fun micCallback(call: PluginCall) {
        if (micGranted()) begin(call) else call.reject(VoiceText.MIC_DENIED, "MIC_DENIED")
    }

    private fun begin(call: PluginCall) {
        val lang = call.getString("lang") ?: "vi-VN"
        activity.runOnUiThread {
            if (!SpeechRecognizer.isRecognitionAvailable(context)) {
                call.reject(VoiceText.NO_RECOGNIZER, "NO_RECOGNIZER")
                return@runOnUiThread
            }
            // Đang đọc trả lời thì dừng để micro không nghe chính giọng đọc.
            tts?.stop()
            recognizer?.destroy()
            val next = SpeechRecognizer.createSpeechRecognizer(context)
            next.setRecognitionListener(listener)
            recognizer = next
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE, lang)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, lang)
                .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            next.startListening(intent)
            call.resolve()
        }
    }

    private fun firstText(bundle: Bundle?): String =
        bundle?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()

    private fun finish() {
        recognizer?.destroy()
        recognizer = null
        notifyListeners("end", JSObject())
    }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) = Unit
        override fun onBeginningOfSpeech() = Unit
        override fun onRmsChanged(rmsdB: Float) = Unit
        override fun onBufferReceived(buffer: ByteArray?) = Unit
        override fun onEndOfSpeech() = Unit
        override fun onEvent(eventType: Int, params: Bundle?) = Unit

        override fun onPartialResults(partialResults: Bundle?) {
            val text = firstText(partialResults)
            if (text.isNotEmpty()) notifyListeners("partial", JSObject().put("text", text))
        }

        override fun onResults(results: Bundle?) {
            notifyListeners("final", JSObject().put("text", firstText(results)))
            finish()
        }

        override fun onError(error: Int) {
            notifyListeners("error", JSObject().put("code", VoiceText.code(error)).put("message", VoiceText.message(error)))
            finish()
        }
    }

    /** Dừng nghe; kết quả đã nghe được vẫn về qua `final`. */
    @PluginMethod
    fun stop(call: PluginCall) {
        activity.runOnUiThread { recognizer?.stopListening() }
        call.resolve()
    }

    /** Bỏ hẳn lượt nghe, không gửi kết quả. */
    @PluginMethod
    fun cancel(call: PluginCall) {
        activity.runOnUiThread {
            if (recognizer != null) {
                recognizer?.cancel()
                finish()
            }
        }
        call.resolve()
    }

    /** Mở TextToSpeech một lần; [then] chạy khi đã biết có đọc được tiếng Việt không. */
    private fun withTts(then: () -> Unit) {
        if (ttsReady != null) {
            then()
            return
        }
        waitingForTts += then
        if (tts != null) return
        tts = TextToSpeech(context) { status ->
            val ready = status == TextToSpeech.SUCCESS
            ttsReady = ready
            if (ready) {
                val engine = tts!!
                ttsVietnamese = VoiceText.ttsLanguageUsable(engine.setLanguage(Locale.forLanguageTag("vi-VN")))
                engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) = Unit
                    override fun onDone(utteranceId: String?) = notifyListeners("speakEnd", JSObject())

                    @Deprecated("Bản API cũ", ReplaceWith(""))
                    override fun onError(utteranceId: String?) = notifyListeners("speakEnd", JSObject())

                    override fun onStop(utteranceId: String?, interrupted: Boolean) = notifyListeners("speakEnd", JSObject())
                })
            }
            val queued = waitingForTts.toList()
            waitingForTts.clear()
            queued.forEach { it() }
        }
    }

    @PluginMethod
    fun speak(call: PluginCall) {
        val text = call.getString("text").orEmpty().trim()
        if (text.isEmpty()) {
            call.resolve()
            return
        }
        withTts {
            when {
                ttsReady != true -> call.reject(VoiceText.TTS_UNAVAILABLE, "TTS_UNAVAILABLE")
                !ttsVietnamese -> call.reject(VoiceText.TTS_NO_VI, "TTS_NO_VI")
                else -> {
                    tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "troly-tra-loi")
                    call.resolve()
                }
            }
        }
    }

    @PluginMethod
    fun stopSpeaking(call: PluginCall) {
        tts?.stop()
        call.resolve()
    }

    @PluginMethod
    fun ttsStatus(call: PluginCall) {
        withTts { call.resolve(JSObject().put("available", ttsReady == true).put("vietnamese", ttsReady == true && ttsVietnamese)) }
    }

    /** Mở cài đặt giọng đọc của máy để tải giọng tiếng Việt; máy không có trang đó thì mở trang tải dữ liệu giọng. */
    @PluginMethod
    fun openTtsSettings(call: PluginCall) {
        val intents = listOf(
            Intent("com.android.settings.TTS_SETTINGS"),
            Intent(TextToSpeech.Engine.ACTION_INSTALL_TTS_DATA),
        )
        for (intent in intents) {
            try {
                activity.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                // Quay lại app thì hỏi lại giọng tiếng Việt.
                ttsReady = null
                tts?.shutdown()
                tts = null
                call.resolve(JSObject().put("opened", true))
                return
            } catch (_: Exception) {
                // thử trang kế
            }
        }
        call.resolve(JSObject().put("opened", false))
    }

    override fun handleOnDestroy() {
        recognizer?.destroy()
        recognizer = null
        tts?.shutdown()
        tts = null
    }
}
