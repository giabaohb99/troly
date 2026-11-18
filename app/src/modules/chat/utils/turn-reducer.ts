import type { SseEvent } from '@/core/api/sse'
import { KNOWN_ACTION_TYPES, type ChatAction, type ChatMessage } from '@/modules/chat/types/chat'

// Trạng thái một lượt chat đang chạy, dựng từ các sự kiện SSE (12-api.md mục 5.2).

export interface ChatTurn {
  clientMessageId: string
  // Tệp người dùng gửi kèm lượt này (để hiện ngay trong bong bóng đang gửi).
  attachments?: { file_id: number; name?: string | null; mime?: string | null }[]
  userText: string
  userMessage: ChatMessage | null
  conversationId: number | null
  text: string
  toolLabel: string | null
  actions: ChatAction[]
  assistant: ChatMessage | null
  status: 'streaming' | 'done' | 'error'
  error: { code: string; message: string } | null
}

export function startTurn(clientMessageId: string, userText: string): ChatTurn {
  return { clientMessageId, userText, userMessage: null, conversationId: null, text: '', toolLabel: null, actions: [], assistant: null, status: 'streaming', error: null }
}

function parse(data: string): Record<string, unknown> | null {
  try {
    const value: unknown = JSON.parse(data)
    return value && typeof value === 'object' ? (value as Record<string, unknown>) : null
  } catch {
    return null
  }
}

export function applyTurnEvent(turn: ChatTurn, event: SseEvent): ChatTurn {
  const data = parse(event.data)
  if (!data) return turn
  switch (event.event) {
    case 'message.created':
      return { ...turn, userMessage: (data.user_message as ChatMessage) ?? null, conversationId: (data.conversation_id as number) ?? null }
    case 'text.delta':
      return { ...turn, text: turn.text + String(data.text ?? ''), toolLabel: null }
    case 'tool.started':
      return { ...turn, toolLabel: typeof data.label === 'string' ? data.label : 'Đang làm...' }
    case 'tool.finished':
      return { ...turn, toolLabel: null }
    case 'action': {
      const action = data as unknown as ChatAction
      if (!KNOWN_ACTION_TYPES.has(action.type)) return turn
      return { ...turn, actions: [...turn.actions.filter((a) => a.id !== action.id), action] }
    }
    case 'message.completed': {
      // Chữ cuối của máy chủ thay chữ chạy dần (trường hợp bị từ chối hoặc sửa giữa chừng).
      const fromServer = (data.assistant_message ?? {}) as Partial<ChatMessage>
      const assistant: ChatMessage = {
        id: fromServer.id ?? -Date.now(),
        role: 'assistant',
        text: typeof fromServer.text === 'string' ? fromServer.text : turn.text,
        model: fromServer.model ?? null,
        citations: fromServer.citations ?? null,
        attachments: fromServer.attachments ?? null,
        actions: fromServer.actions ?? turn.actions,
        status: fromServer.status ?? 'done',
        created_at: fromServer.created_at ?? new Date().toISOString(),
      }
      return { ...turn, assistant, text: assistant.text, actions: assistant.actions ?? [], toolLabel: null, status: 'done' }
    }
    case 'error':
      return { ...turn, status: 'error', toolLabel: null, error: { code: String(data.code ?? 'UNKNOWN'), message: String(data.message ?? 'Trợ lý đang lỗi, thử lại sau.') } }
    default:
      return turn
  }
}

// Luồng đóng mà chưa có message.completed hay error: coi như mất kết nối, máy chủ vẫn chạy hết lượt.
export function finishTurnWithoutCompletion(turn: ChatTurn): ChatTurn {
  if (turn.status !== 'streaming') return turn
  return { ...turn, status: 'error', toolLabel: null, error: { code: 'STREAM_INTERRUPTED', message: 'Mất kết nối giữa chừng. Đang tải lại câu trả lời.' } }
}
