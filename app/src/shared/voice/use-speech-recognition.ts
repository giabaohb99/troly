import { useCallback, useEffect, useRef, useState } from 'react'
import { isNative } from '@/core/config'
import { Voice } from '@/core/native/voice'

// Nhận giọng nói (30 mục 3.4). Trên Android: plugin Voice (SpeechRecognizer, vì WebView không có Web Speech; lỗi
// bản 1.0.5 là nút micro tự ẩn). Trên trình duyệt: Web Speech API.
// Kiểu tự khai vì thư viện DOM của TypeScript chưa có đủ.
interface RecognitionAlternative {
  transcript: string
}
interface RecognitionResult {
  isFinal: boolean
  0: RecognitionAlternative
}
interface RecognitionEvent {
  resultIndex: number
  results: ArrayLike<RecognitionResult>
}
interface Recognition {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((event: RecognitionEvent) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}
type RecognitionConstructor = new () => Recognition

function getRecognitionConstructor(): RecognitionConstructor | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

const ERROR_MESSAGES: Record<string, string> = {
  'not-allowed': 'Chưa cho phép dùng micro. Mở quyền micro cho trang này rồi thử lại.',
  'no-speech': 'Em chưa nghe thấy gì, nói lại nhé.',
  network: 'Nhận giọng nói cần mạng, kiểm tra kết nối rồi thử lại.',
  'audio-capture': 'Không tìm thấy micro.',
}

interface SpeechRecognitionOptions {
  onFinal: (text: string) => void
  onError: (message: string) => void
}

function useWebSpeech({ onFinal, onError }: SpeechRecognitionOptions) {
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const recognitionRef = useRef<Recognition | null>(null)
  const finalRef = useRef('')
  const handlersRef = useRef({ onFinal, onError })
  const supported = typeof window !== 'undefined' && getRecognitionConstructor() !== null

  useEffect(() => {
    handlersRef.current = { onFinal, onError }
  }, [onFinal, onError])

  useEffect(() => () => recognitionRef.current?.abort(), [])

  const start = useCallback(() => {
    const Ctor = getRecognitionConstructor()
    if (!Ctor || recognitionRef.current) return
    const recognition = new Ctor()
    recognition.lang = 'vi-VN'
    recognition.interimResults = true
    recognition.continuous = false
    finalRef.current = ''
    recognition.onresult = (event) => {
      let interimText = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) finalRef.current += result[0].transcript
        else interimText += result[0].transcript
      }
      setInterim(finalRef.current + interimText)
    }
    recognition.onerror = (event) => {
      if (event.error !== 'aborted') handlersRef.current.onError(ERROR_MESSAGES[event.error] ?? `Lỗi nhận giọng nói: ${event.error}`)
    }
    recognition.onend = () => {
      recognitionRef.current = null
      setListening(false)
      setInterim('')
      const text = finalRef.current.trim()
      if (text) handlersRef.current.onFinal(text)
    }
    recognitionRef.current = recognition
    setListening(true)
    recognition.start()
  }, [])

  const stop = useCallback(() => recognitionRef.current?.stop(), [])

  return { supported, listening, interim, start, stop }
}

// Bản Android: lớp gốc nghe, gửi kết quả tạm (partial), kết quả cuối (final), lỗi, rồi end. Nút micro luôn hiện; máy
// không có dịch vụ nhận giọng thì bấm sẽ báo lỗi rõ thay vì ẩn nút.
function useNativeSpeech({ onFinal, onError }: SpeechRecognitionOptions) {
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const finalRef = useRef('')
  const handlersRef = useRef({ onFinal, onError })

  useEffect(() => {
    handlersRef.current = { onFinal, onError }
  }, [onFinal, onError])

  useEffect(() => {
    const handles = [
      Voice.addListener('partial', (e) => setInterim(e.text)),
      Voice.addListener('final', (e) => {
        finalRef.current = e.text
      }),
      Voice.addListener('error', (e) => handlersRef.current.onError(e.message)),
      Voice.addListener('end', () => {
        setListening(false)
        setInterim('')
        const text = finalRef.current.trim()
        finalRef.current = ''
        if (text) handlersRef.current.onFinal(text)
      }),
    ]
    return () => {
      void Voice.cancel().catch(() => null)
      handles.forEach((h) => void h.then((x) => x.remove()))
    }
  }, [])

  const start = useCallback(async () => {
    finalRef.current = ''
    setInterim('')
    setListening(true)
    try {
      await Voice.start({ lang: 'vi-VN' })
    } catch (error) {
      setListening(false)
      handlersRef.current.onError((error as { message?: string })?.message || 'Không bắt đầu nghe được.')
    }
  }, [])

  const stop = useCallback(() => void Voice.stop().catch(() => null), [])

  return { supported: true, listening, interim, start: () => void start(), stop }
}

export const useSpeechRecognition = isNative ? useNativeSpeech : useWebSpeech
