import { useCallback, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '@/core/api/api-error'
import { postEventStream } from '@/core/api/sse'
import { getChatStatus, getChatToday } from '@/modules/chat/api/chat-api'
import type { ChatMessage, ChatMode, ChatToday } from '@/modules/chat/types/chat'
import { applyTurnEvent, finishTurnWithoutCompletion, startTurn, type ChatTurn } from '@/modules/chat/utils/turn-reducer'
import { queryKeys } from '@/shared/constants/query-keys'

export function useChatToday() {
  return useQuery({ queryKey: queryKeys.chat.today, queryFn: getChatToday })
}

export function useChatStatus() {
  return useQuery({ queryKey: queryKeys.chat.status, queryFn: getChatStatus, staleTime: 60_000 })
}

export interface SendInput {
  text: string
  mode: ChatMode
  fileIds: number[]
}

// Một lượt chat qua SSE: hiện chữ chạy dần, nhãn công cụ, hành động; xong thì ghép vào danh sách tin hôm nay.
export function useChatTurn() {
  const queryClient = useQueryClient()
  const [turn, setTurn] = useState<ChatTurn | null>(null)
  const busyRef = useRef(false)
  const lastInputRef = useRef<SendInput | null>(null)

  const run = useCallback(
    async (input: SendInput, clientMessageId: string) => {
      if (busyRef.current) return
      busyRef.current = true
      lastInputRef.current = input
      let current = startTurn(clientMessageId, input.text)
      setTurn(current)
      try {
        await postEventStream(
          '/chat/messages',
          { client_message_id: clientMessageId, text: input.text, attachment_file_ids: input.fileIds, mode: input.mode },
          (event) => {
            current = applyTurnEvent(current, event)
            setTurn(current)
          },
        )
        current = finishTurnWithoutCompletion(current)
      } catch (error) {
        const apiError = error instanceof ApiError ? error : new ApiError(0, 'Trợ lý đang lỗi, thử lại sau.', 'UNKNOWN')
        current = { ...current, status: 'error', toolLabel: null, error: { code: apiError.code, message: apiError.message } }
      } finally {
        busyRef.current = false
      }

      if (current.status === 'done' && current.assistant) {
        const done = current
        const userMessage: ChatMessage = done.userMessage ?? {
          id: -Date.now(),
          role: 'user',
          text: done.userText,
          model: null,
          citations: null,
          attachments: null,
          actions: null,
          status: 'done',
          created_at: new Date().toISOString(),
        }
        queryClient.setQueryData<ChatToday>(queryKeys.chat.today, (old) =>
          old ? { ...old, messages: [...old.messages, userMessage, done.assistant as ChatMessage] } : old,
        )
        setTurn(null)
        void queryClient.invalidateQueries({ queryKey: queryKeys.chat.today })
        void queryClient.invalidateQueries({ queryKey: queryKeys.chat.status })
        return
      }
      setTurn(current)
      // Máy chủ vẫn chạy hết lượt khi mất kết nối giữa chừng: tải lại tin hôm nay để lấy câu trả lời.
      if (current.error?.code === 'STREAM_INTERRUPTED') {
        await queryClient.invalidateQueries({ queryKey: queryKeys.chat.today })
        setTurn(null)
      }
    },
    [queryClient],
  )

  const send = useCallback((input: SendInput) => run(input, crypto.randomUUID()), [run])

  // Gửi lại cùng client_message_id: máy chủ trả câu trả lời cũ nếu lượt đã xong (12-api.md mục 3.8).
  const retry = useCallback(() => {
    if (turn && lastInputRef.current) void run(lastInputRef.current, turn.clientMessageId)
  }, [run, turn])

  const dismiss = useCallback(() => setTurn(null), [])

  return { turn, send, retry, dismiss, busy: turn?.status === 'streaming' }
}
