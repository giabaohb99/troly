import { useCallback, useEffect, useRef, useState } from 'react'

// Web Speech API (nhận giọng nói của trình duyệt). Trong WebView Android thường không có: nút micro tự ẩn; plugin Voice làm sau (30 mục 3.4).
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

export function useSpeechRecognition({ onFinal, onError }: SpeechRecognitionOptions) {
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
