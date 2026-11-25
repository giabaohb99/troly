import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '@/core/api/api-error'
import { postEventStream } from '@/core/api/sse'
import { Alarm } from '@/core/native/alarm'
import { isAppActive, onAppActiveChange } from '@/core/native/app-state'
import { getChatStatus, getChatToday, getSession } from '@/modules/chat/api/chat-api'
import type { ChatMessage, ChatMode, ChatToday } from '@/modules/chat/types/chat'
import { applyTurnEvent, finishTurnWithoutCompletion, startTurn, type ChatTurn } from '@/modules/chat/utils/turn-reducer'
import { queryKeys } from '@/shared/constants/query-keys'

// Khóa cache của phiên đang mở: không chọn phiên là /chat/today (phiên hoạt động gần nhất), có thì phiên đó (QĐ-51).
export const chatViewKey = (sessionId: number | null) => (sessionId ? queryKeys.chat.session(sessionId) : queryKeys.chat.today)

// Chuyển tab rồi quay lại: dùng ngay dữ liệu đã có, không tải lại nếu vừa tải trong 1 phút (sau lượt chat vẫn tải).
export function useChatView(sessionId: number | null) {
  return useQuery({ queryKey: chatViewKey(sessionId), queryFn: () => (sessionId ? getSession(sessionId) : getChatToday()), staleTime: 60_000 })
}

export function useChatToday() {
  return useChatView(null)
}

export function useChatStatus() {
  return useQuery({ queryKey: queryKeys.chat.status, queryFn: getChatStatus, staleTime: 60_000 })
}

export interface SendInput {
  text: string
  mode: ChatMode
  fileIds: number[]
  // Lượt này dùng công cụ của các kết nối đã nối (QĐ-56).
  connectors?: boolean
}

// Một lượt chat qua SSE: hiện chữ chạy dần, nhãn công cụ, hành động; xong thì ghép vào phiên đang mở.
// conversationId: phiên nhận tin (QĐ-51); null là phiên hoạt động gần nhất như trước.
export function useChatTurn(viewKey: readonly unknown[] = queryKeys.chat.today, conversationId: number | null = null) {
  const queryClient = useQueryClient()
  const conversationRef = useRef(conversationId)
  conversationRef.current = conversationId
  const [turn, setTurn] = useState<ChatTurn | null>(null)
  const busyRef = useRef(false)
  const lastInputRef = useRef<SendInput | null>(null)

  // Gửi tin rồi rời app khi lượt chưa xong: nhờ lớp gốc hỏi notice chat_done dày hơn vài phút, phòng khi WebView
  // bị dừng lúc chạy nền (QĐ-41).
  useEffect(
    () =>
      onAppActiveChange((active) => {
        if (!active && busyRef.current) void Alarm.startNoticeBurst()
      }),
    [],
  )

  const run = useCallback(
    async (input: SendInput, clientMessageId: string) => {
      if (busyRef.current) return
      busyRef.current = true
      lastInputRef.current = input
      let current: ChatTurn = { ...startTurn(clientMessageId, input.text), attachments: input.fileIds.map((id) => ({ file_id: id })) }
      let usedTool = false
      setTurn(current)
      try {
        await postEventStream(
          '/chat/messages',
          {
            client_message_id: clientMessageId,
            text: input.text,
            attachment_file_ids: input.fileIds,
            mode: input.mode,
            ...(conversationRef.current ? { conversation_id: conversationRef.current } : {}),
            ...(input.connectors ? { use_connectors: true } : {}),
          },
          (event) => {
            if (event.event === 'tool.started') usedTool = true
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
      // Trợ lý vừa chạy công cụ (có thể đã tạo, sửa lịch, việc, nhắc): tải lại nhắc ngay để đặt báo thức, kể cả
      // nhắc chỉ còn vài phút; lịch, việc trên màn cũng tải lại.
      if (usedTool) {
        void Alarm.sync()
        void queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all })
      }

      if (current.status === 'done' && current.assistant) {
        const done = current
        // Lượt xong mà app đang ở màn hình: ghi đã xem để notice chat_done của máy chủ không báo lại (lỗi 1.0.2).
        if (isAppActive() && done.assistant && done.assistant.id > 0) void Alarm.markChatSeen({ messageIds: [done.assistant.id] })
        // Lượt xong khi app không ở màn hình: tự báo ngay; lớp gốc chống báo trùng theo id tin.
        if (!isAppActive() && done.assistant && done.assistant.id > 0) {
          const id = done.assistant.id
          const link = `troly://?${done.conversationId ? `phien=${done.conversationId}&` : ''}tin=${id}`
          const fileAction = done.assistant.actions?.find((a) => a.type === 'file')
          const file = fileAction && fileAction.type === 'file' ? { file_id: fileAction.file_id, name: fileAction.name } : done.assistant.attachments?.[0]
          void Alarm.notifyChatDone({
            messageId: String(id),
            deepLink: link,
            body: done.assistant.text.slice(0, 120) || (file ? `Đã xuất ${file.name}` : null),
            fileLink: file ? `${link}&mo-tep=${file.file_id}` : null,
          })
        }
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
        queryClient.setQueryData<ChatToday>(viewKey, (old) =>
          old ? { ...old, messages: [...old.messages, userMessage, done.assistant as ChatMessage] } : old,
        )
        setTurn(null)
        void queryClient.invalidateQueries({ queryKey: viewKey })
        void queryClient.invalidateQueries({ queryKey: queryKeys.chat.today })
        void queryClient.invalidateQueries({ queryKey: queryKeys.chat.sessionsAll })
        void queryClient.invalidateQueries({ queryKey: queryKeys.chat.status })
        // Máy chủ đặt tên phiên ở luồng nền sau câu trả lời đầu: hỏi lại một lần sau 5 giây để hiện tên mới.
        if (!queryClient.getQueryData<ChatToday>(viewKey)?.conversation?.title) {
          window.setTimeout(() => {
            void queryClient.invalidateQueries({ queryKey: viewKey })
            void queryClient.invalidateQueries({ queryKey: queryKeys.chat.sessionsAll })
          }, 5_000)
        }
        return
      }
      setTurn(current)
      // Máy chủ vẫn chạy hết lượt khi mất kết nối giữa chừng: tải lại tin hôm nay để lấy câu trả lời.
      if (current.error?.code === 'STREAM_INTERRUPTED') {
        await queryClient.invalidateQueries({ queryKey: viewKey })
        setTurn(null)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- viewKey đổi theo phiên; màn chat dựng lại khi đổi phiên
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
