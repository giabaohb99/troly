import { useSyncExternalStore } from 'react'

// Cài đặt giọng nói lưu trên máy (1.0.6): đọc to câu trả lời khi hỏi bằng giọng, mặc định bật.
const KEY = 'troly.voice.read_replies'
const listeners = new Set<() => void>()

export function getReadReplies(): boolean {
  try {
    return localStorage.getItem(KEY) !== 'off'
  } catch {
    return true
  }
}

export function setReadReplies(on: boolean) {
  try {
    localStorage.setItem(KEY, on ? 'on' : 'off')
  } catch {
    // Không lưu được thì giữ mặc định.
  }
  listeners.forEach((l) => l())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useReadReplies(): boolean {
  return useSyncExternalStore(subscribe, getReadReplies, () => true)
}
