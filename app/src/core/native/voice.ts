import { registerPlugin, WebPlugin, type PluginListenerHandle } from '@capacitor/core'

// Nói với trợ lý (30 mục 3.4, bản 1.0.6). Trên Android: VoicePlugin.kt (SpeechRecognizer nhận giọng, TextToSpeech đọc
// trả lời). Trên trình duyệt: nhận giọng dùng Web Speech trong hook, đọc trả lời dùng speechSynthesis.

export interface VoiceError {
  code: string
  message: string
}

export interface VoicePlugin {
  isAvailable(): Promise<{ recognition: boolean; micGranted: boolean }>
  start(options: { lang: string }): Promise<void>
  stop(): Promise<void>
  cancel(): Promise<void>
  speak(options: { text: string }): Promise<void>
  stopSpeaking(): Promise<void>
  ttsStatus(): Promise<{ available: boolean; vietnamese: boolean }>
  openTtsSettings(): Promise<{ opened: boolean }>
  addListener(event: 'partial' | 'final', listener: (event: { text: string }) => void): Promise<PluginListenerHandle>
  addListener(event: 'error', listener: (event: VoiceError) => void): Promise<PluginListenerHandle>
  addListener(event: 'end' | 'speakEnd', listener: () => void): Promise<PluginListenerHandle>
}

function vietnameseVoice(): SpeechSynthesisVoice | null {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return null
  return window.speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith('vi')) ?? null
}

class VoiceWeb extends WebPlugin {
  async isAvailable() {
    return { recognition: false, micGranted: false }
  }
  async start() {}
  async stop() {}
  async cancel() {}

  async speak({ text }: { text: string }) {
    const voice = vietnameseVoice()
    if (!voice) throw Object.assign(new Error('Trình duyệt chưa có giọng đọc tiếng Việt.'), { code: 'TTS_NO_VI' })
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.voice = voice
    utterance.lang = voice.lang
    utterance.onend = () => this.notifyListeners('speakEnd', {})
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(utterance)
  }

  async stopSpeaking() {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel()
  }

  async ttsStatus() {
    const has = typeof window !== 'undefined' && 'speechSynthesis' in window
    return { available: has, vietnamese: has && vietnameseVoice() !== null }
  }

  async openTtsSettings() {
    return { opened: false }
  }
}

export const Voice = registerPlugin<VoicePlugin>('Voice', { web: () => new VoiceWeb() as unknown as VoicePlugin })

export const TTS_NO_VI = 'TTS_NO_VI'
